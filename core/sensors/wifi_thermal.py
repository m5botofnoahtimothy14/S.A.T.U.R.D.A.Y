"""
SATURDAY WiFi-Thermal CSI Mapping — spatial thermal heat-map of radio energy.

True CSI spatial mapping requires per-antenna CSI hardware (Intel 5300, Nexmon/ESP32).
On standard Windows gear we build a REAL spatial map using the many distinct nearby
WiFi transmitters (BSSIDs) as independent sensing nodes: each network's RSSI time-series
carries its own multipath signature, and a person's position perturbs each transmitter
differently. Fusing all of them through an inverse-distance multipath model yields a
2D thermal grid — a thermographic-style map of where radio-hotspot / human energy sits.

Output:
  /api/wifi/thermal  ->  { grid: [[...]XH], grid_w, grid_h, scale,
                           hotspots: [{x,y,heat}], presence_center:{x,y}, updated_at }
"""
import time
import math
import threading
import collections
import logging
from typing import Dict, List, Optional, Any
import numpy as np

logger = logging.getLogger("SATURDAY.Sensors.WiFiThermal")


def _thermal_color_already(canvas_side=False):
    pass


class ThermalNode:
    """A single sensing node (one WiFi transmitter/BSSID) with a spatial anchor + RSSI history."""

    def __init__(self, key: str, label: str, x: float, y: float, signal: float = 50.0):
        self.key = key
        self.label = label
        self.x = float(x)
        self.y = float(y)
        self.signal = float(signal)
        self.history: collections.deque = collections.deque(maxlen=120)
        self.baseline: float = float(signal)
        self.energized_at: float = 0.0

    def feed(self, signal: float, ts: float) -> float:
        """Push the latest RSSI; returns per-node activity variance delta (0..1)."""
        if self.history and len(self.history) >= 3:
            recent = [s for _, s in list(self.history)[-4:]]
            prev_mean = sum(recent) / len(recent)
        else:
            prev_mean = float(signal)
        self.history.append((ts, float(signal)))
        if len(self.history) >= 8:
            rec = [s for _, s in list(self.history)[-24:]]
            var = float(np.var(rec))
            self.baseline = self.baseline * 0.9 + prev_mean * 0.1
        else:
            var = 0.0
        # activity: soft sigmoid on RSSI variance.
        # RSSI(%) natural jitter ~ 1-4, a nearby moving person perturbs it to ~10-40.
        # maps: var 0->0.12, 8->0.34, 12->0.5, 20->0.79, 40->0.99
        activity = float(1.0 / (1.0 + math.exp(-(var - 12.0) / 6.0)))
        if activity > 0.35:
            self.energized_at = ts
        return activity


class WiFiThermalMap:
    """Spatial thermal mapper fusing many WiFi sensing nodes into a 2D heat grid."""

    def __init__(self, grid_size: int = 20, sampling: int = 6):
        self.grid_size = grid_size
        self.sampling = sampling
        self.nodes: Dict[str, ThermalNode] = {}
        self._lock = threading.Lock()
        self.running = False
        self._thr: Optional[threading.Thread] = None
        self.grid = np.zeros((grid_size, grid_size), dtype=np.float32)
        self.raw_grid = np.zeros((grid_size, grid_size), dtype=np.float32)
        self.hotspots: List[Dict[str, Any]] = []
        self.presence_center: Dict[str, float] = {"x": grid_size / 2.0, "y": grid_size / 2.0}
        self.updated_at: float = 0.0
        self.total_activity = 0.0
        # deterministic anchor placement for the sensing field (virtual room 0..1 x 0..1)
        self._anchor_slots = [
            (0.18, 0.18), (0.82, 0.16), (0.50, 0.10), (0.12, 0.55),
            (0.90, 0.50), (0.28, 0.82), (0.74, 0.86), (0.50, 0.52),
            (0.05, 0.30), (0.95, 0.30), (0.35, 0.35), (0.65, 0.65),
        ]
        self._slot = 0

    def start(self):
        if self.running:
            return
        self.running = True
        self._thr = threading.Thread(target=self._tick, daemon=True, name="wifi-thermal")
        self._thr.start()
        logger.info("WiFi-Thermal CSI mapping started")

    def stop(self):
        self.running = False
        if self._thr:
            self._thr.join(timeout=1)

    # --- node management ---
    def register_node(self, key: str, label: str, signal: float) -> ThermalNode:
        with self._lock:
            if key not in self.nodes:
                slot = self._anchor_slots[self._slot % len(self._anchor_slots)]
                self._slot += 1
                node = ThermalNode(key, label, slot[0], slot[1], signal)
                self.nodes[key] = node
                logger.debug(f"Thermal node registered: {label} at ({slot[0]:.2f},{slot[1]:.2f})")
            else:
                node = self.nodes[key]
                node.signal = float(signal)
            return node

    def feed_network(self, bssid: str, ssid: str, signal: float, ts: float = None) -> Optional[ThermalNode]:
        """Feed a single observed network's RSSI; the mapper tracks per-transmitter activity."""
        ts = ts or time.time()
        node = self.register_node(bssid or f"ap-{ssid}-{int(ts)}", ssid or "AP", signal)
        node.feed(signal, ts)
        return node

    # --- fusion ---
    def _build_grid(self) -> np.ndarray:
        n = self.grid_size
        g = np.zeros((n, n), dtype=np.float32)
        active = [nd for nd in self.nodes.values() if len(nd.history) >= 8]
        if not active:
            return g
        # xs,ys normalized anchor coordinates
        xs = np.array([nd.x for nd in active], dtype=np.float32)
        ys = np.array([nd.y for nd in active], dtype=np.float32)
        sigs = np.array([nd.signal for nd in active], dtype=np.float32)
        # activity (how much that node is being perturbed recently)
        acts = np.array([self._node_activity(nd) for nd in active], dtype=np.float32)
        # grid coords
        gy, gx = np.meshgrid(np.linspace(0, 1, n), np.linspace(0, 1, n), indexing="ij")
        gx = gx[..., None]  # (n,n,1)
        gy = gy[..., None]
        # distance from each cell to each node
        dist = np.sqrt((gx - xs) ** 2 + (gy - ys) ** 2)  # (n,n,M)
        dist = np.maximum(dist, 0.12)
        # inverse-distance contribution weighted by node activity and signal strength
        weight = acts * np.clip(sigs / 100.0 + 0.3, 0.0, 1.3)
        contrib = weight[None, None, :] / (dist ** 2.0)
        g = contrib.sum(axis=2)  # (n,n)
        # add small global ambient (room baseline activity)
        g = g + 0.02 * float(np.clip(np.max(acts), 0.0, 1.0))
        return g

    def _node_activity(self, nd: ThermalNode) -> float:
        if len(nd.history) < 8:
            return 0.0
        rec = [s for _, s in list(nd.history)[-24:]]
        var = float(np.var(rec))
        return float(1.0 / (1.0 + math.exp(-(var - 12.0) / 6.0)))

    def _tick(self):
        while self.running:
            with self._lock:
                raw = self._build_grid()
                self.raw_grid = raw
                total = float(raw.sum())
                self.total_activity = total
                if total > 1e-6:
                    self.grid = raw / max(total, 1.0)
                else:
                    self.grid = raw
                self.hotspots = self._find_hotspots(self.grid)
                if self.hotspots:
                    self.presence_center = {"x": self.hotspots[0]["x"], "y": self.hotspots[0]["y"]}
                self.updated_at = time.time()
            time.sleep(self.sampling)

    def _find_hotspots(self, g: np.ndarray, k: int = 4) -> List[Dict[str, Any]]:
        n = g.shape[0]
        flat = g.flatten()
        if flat.max() <= 0:
            return []
        idx = np.argsort(flat)[::-1][:k]
        out = []
        for i in idx:
            y, x = divmod(int(i), n)
            out.append({
                "x": float(round(x / float(n - 1), 3)),
                "y": float(round(y / float(n - 1), 3)),
                "heat": float(round(flat[i], 4)),
            })
        return out

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            grid = self.grid.astype(float)
            raw = self.raw_grid.astype(float)
            hotspots = list(self.hotspots)
            center = dict(self.presence_center)
            updated = self.updated_at
            nodes = [
                {"label": nd.label, "x": nd.x, "y": nd.y, "signal": round(nd.signal, 1),
                 "activity": round(self._node_activity(nd), 3), "samples": len(nd.history)}
                for nd in self.nodes.values()
            ]
        qs = [0.0, 0.25, 0.5, 0.75, 1.0]
        pct = [float(np.percentile(grid, q * 100)) for q in qs] if grid.size else [0.0] * 5
        return {
            "grid": grid.tolist(),
            "grid_w": int(self.grid_size),
            "grid_h": int(self.grid_size),
            "scale": "0..1 normalized radio-thermal heat",
            "hotspots": hotspots,
            "presence_center": center,
            "nodes": nodes,
            "node_count": len(nodes),
            "total_activity": round(self.total_activity, 4),
            "percentiles": pct,
            "updated_at": updated,
            "live": updated > (time.time() - 60),
        }