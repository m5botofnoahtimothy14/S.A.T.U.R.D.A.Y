// SATURDAY front door — Vercel serverless proxy to the home tunnel.
//
// Why: the tunnel URL/token live on the PC; the browser can't know them.
// This function holds the secrets as Vercel env vars (server-side, never
// shipped to the browser) and relays same-origin /api/* calls.
//
// BACKEND DISCOVERY (first hit wins):
//   1. ?api= hint (any https URL — phone bookmark after `share on`)
//   2. Firebase presence (see below) — survives tunnel URL rotation
//   3. Static SAT_API env (stable --hostname / Zero Trust setups)
//
// Env (Vercel → Settings → Environment Variables):
//   SAT_API    https://<stable-tunnel-host>   (fallback for fixed hostnames)
//   SAT_TOKEN  <dashboard token>               (required — use the pinned
//              SATURDAY_SHARED_TOKEN value so restarts never re-link)
//   SAT_PIN    <a PIN you invent>              (optional but STRONGLY advised)
//   --- auto-discovery (recommended, kills rotation breakage) ---
//   SAT_FIREBASE_SA  <full service-account JSON, one line> (server-side only)
//   SAT_DB_URL       https://<project>-default-rtdb.<region>.firebasedatabase.app
//   SAT_NODE         saturday-node (must match the PC's FIREBASE_NODE_ID)
//   The PC writes its live tunnel URL to RTDB presence every 60s; this
//   proxy reads it here. Laptop asleep >3min → presence stale → 503 with
//   a truthful "asleep" message instead of a hanging fetch.
//
// Hobby limits are honest: functions time out (~60s), so instant commands
// (status, sense, bot moves, heal) fly; multi-minute brain/research runs
// belong to direct mode or the local CLI.

let _admin = null;
let _presenceCache = { url: "", at: 0 };

function adminDb() {
  const sa = (process.env.SAT_FIREBASE_SA || "").trim();
  const dbUrl = (process.env.SAT_DB_URL || "").trim();
  if (!sa || !dbUrl) return null;
  try {
    if (!_admin) {
      const admin = require("firebase-admin");
      if (!admin.apps.length) {
        admin.initializeApp({
          credential: admin.credential.cert(JSON.parse(sa)),
          databaseURL: dbUrl,
        });
      }
      _admin = admin;
    }
    return _admin.database();
  } catch (e) {
    return null;
  }
}

async function presenceUrl() {
  const now = Date.now();
  if (_presenceCache.url && now - _presenceCache.at < 30000) {
    return _presenceCache.url; // 30s cache: RTDB reads cost nothing, latency does
  }
  try {
    const db = adminDb();
    if (!db) return "";
    const node = (process.env.SAT_NODE || "saturday-node").trim();
    const snap = await db.ref(`/saturday_system/${node}/status/presence`).once("value");
    const p = snap.val() || {};
    const ageS = now / 1000 - (p.ts || 0);
    const url = String(p.tunnel_url || "").trim();
    if (p.online && url.startsWith("https://") && ageS < 180) {
      _presenceCache = { url, at: now };
      return url;
    }
    _presenceCache = { url: "", at: now };
    return "";
  } catch (e) {
    return "";
  }
}

function cleanQuery(search) {  const q = new URLSearchParams(search || "");
  q.delete("pin");
  q.delete("path");
  const s = q.toString();
  return s ? "?" + s : "";
}

module.exports = async function handler(req, res) {
  try {
    const pin = req.headers["x-sat-pin"] || (req.query && req.query.pin) || "";
    if (process.env.SAT_PIN && pin !== process.env.SAT_PIN) {
      return res.status(401).json({ error: "pin required" });
    }
    // 1. explicit backend hint wins (HUD passes its stored tunnel URL through).
    // Accepts ANY https host now (stable hostnames, custom domains) — not
    // just trycloudflare. This makes the proxy immune to stale env values.
    let base = "";
    try {
      const hint = req.query && req.query.api ? String(req.query.api).trim() : "";
      if (/^https:\/\/[a-z0-9.-]+(:\d+)?(\/.*)?$/i.test(hint)) {
        base = hint.replace(/\/$/, "");
      }
    } catch (e) { /* env fallback */ }
    // 2. live presence from RTDB (rotation-proof).
    if (!base) base = await presenceUrl();
    // 3. static fallback env.
    if (!base) base = (process.env.SAT_API || "").trim().replace(/\/$/, "");
    const token = (process.env.SAT_TOKEN || "").trim();
    if (!base) {
      return res.status(503).json({
        error: "backend unreachable: no live presence (<3min), no ?api= hint, no SAT_API. " +
               "If the laptop is asleep, wake it — RTDB presence resumes in ~60s. " +
               "If awake, open `share on` and re-link, or set SAT_FIREBASE_SA/SAT_DB_URL for auto-discovery.",
      });
    }
    // path comes from the vercel.json rewrite (/api/sat/:path* -> ?path=)
    // or legacy [...sat] query form.
    let sub = "";
    if (req.query && typeof req.query.path === "string" && req.query.path) {
      sub = req.query.path.replace(/^\/+/, "");
    } else if (Array.isArray(req.query && req.query.sat)) {
      sub = req.query.sat.join("/");
    }
    const target = base + "/" + sub + cleanQuery(req.url.split("?")[1] || "");
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 55000);
    try {
      const init = {
        method: req.method,
        headers: { "Content-Type": "application/json" },
        signal: ctrl.signal,
      };
      if (token) init.headers["X-Saturday-Token"] = token;
      if (req.method !== "GET" && req.method !== "HEAD" && req.body) {
        init.body = typeof req.body === "string" ? req.body : JSON.stringify(req.body);
      }
      const upstream = await fetch(target, init);
      const text = await upstream.text();
      res.status(upstream.status);
      res.setHeader("Content-Type", upstream.headers.get("content-type") || "application/json");
      return res.send(text);
    } finally {
      clearTimeout(timer);
    }
  } catch (e) {
    const msg = String((e && e.message) || e);
    const asleep = /abort/i.test(msg);
    return res.status(502).json({
      error: asleep
        ? "tunnel timed out mid-flight (laptop may have slept). Retry — presence re-resolves."
        : "tunnel unreachable: " + msg.slice(0, 160),
    });
  }
};

// Test hook (no production effect): reset the 30s presence cache.
module.exports._testReset = () => { _presenceCache = { url: "", at: 0 }; };
