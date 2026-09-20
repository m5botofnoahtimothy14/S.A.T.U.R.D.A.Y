"""
============================================================
SATURDAY LOCALIZATION
Hybrid Positioning & Spatial Awareness System
============================================================

Responsibilities:
- Persistent home/dock location
- Local XY coordinate tracking
- Encoder odometry integration
- IMU heading integration
- Wi-Fi environment fingerprinting
- Bluetooth/BLE beacon hooks
- GPS hooks for outdoor operation
- Localization confidence scoring
- Sensor-source fusion
- Last-known-good position
- Distance and bearing calculations
- Localization health monitoring

DESIGN PRINCIPLE:

    Localization does NOT control motors.

    It answers:

        Where am I?
        Where is home?
        How confident am I?
        Which positioning sources are available?

Coordinate Frame:

                +Y Forward
                   ^
                   |
                   |
                   ●──────> +X

Heading:

    0°   = +Y
    90°  = +X
    180° = -Y
    -90° = -X

============================================================
"""

import time
import math
import gc

try:
    import json
except Exception:
    json = None

try:
    import os
except Exception:
    os = None


# ============================================================
# LOCALIZATION SOURCE TYPES
# ============================================================

SOURCE_NONE = "none"
SOURCE_ODOMETRY = "odometry"
SOURCE_IMU = "imu"
SOURCE_WIFI = "wifi"
SOURCE_BLE = "ble"
SOURCE_GPS = "gps"
SOURCE_FUSED = "fused"


# ============================================================
# DEFAULT SETTINGS
# ============================================================

DEFAULT_METERS_PER_TICK = 0.00005

DEFAULT_HOME_FILE = "saturday_home.json"

DEFAULT_POSITION_CONFIDENCE = 0.0

POSITION_STALE_MS = 5000

HOME_ZONE_RADIUS = 2.0

BLE_HOME_ZONE_RADIUS = 3.0

GPS_HOME_ZONE_RADIUS = 10.0


class Localization:
    """
    SATURDAY Hybrid Localization Engine.

    This module owns spatial knowledge.

    Other modules should ask Localization for position rather
    than independently calculating coordinates.

    Example:

        localization.get_position()

        localization.get_home()

        localization.distance_to_home()

        localization.bearing_to_home()

    """

    def __init__(
        self,
        drivers=None,
        config=None
    ):

        print("[LOCALIZATION] Initializing spatial awareness...")

        self.drivers = drivers
        self.config = config

        # ----------------------------------------------------
        # CONFIGURATION
        # ----------------------------------------------------

        self.meters_per_tick = self._get_config(
            "meters_per_tick",
            DEFAULT_METERS_PER_TICK
        )

        self.home_file = self._get_config(
            "home_file",
            DEFAULT_HOME_FILE
        )

        self.home_zone_radius = self._get_config(
            "home_zone_radius",
            HOME_ZONE_RADIUS
        )

        # ----------------------------------------------------
        # CURRENT LOCAL POSITION
        # ----------------------------------------------------

        self.position = {

            "x": 0.0,

            "y": 0.0,

            "heading": 0.0,

            "timestamp": time.ticks_ms(),

            "source": SOURCE_NONE,

            "confidence": DEFAULT_POSITION_CONFIDENCE

        }

        # ----------------------------------------------------
        # LAST KNOWN GOOD POSITION
        # ----------------------------------------------------

        self.last_known_position = None

        # ----------------------------------------------------
        # HOME / DOCK POSITION
        # ----------------------------------------------------

        self.home = {

            "x": 0.0,

            "y": 0.0,

            "heading": 0.0,

            "timestamp": 0,

            "wifi_signature": [],

            "ble_beacon": None,

            "gps": None,

            "confidence": 0.0

        }

        self.home_initialized = False

        # ----------------------------------------------------
        # ENCODER STATE
        # ----------------------------------------------------

        self.last_encoders = None

        self.encoder_initialized = False

        self.encoder_confidence = 0.0

        # ----------------------------------------------------
        # IMU STATE
        # ----------------------------------------------------

        self.imu_available = False

        self.imu_confidence = 0.0

        self.last_heading = None

        # ----------------------------------------------------
        # WIFI LOCALIZATION
        # ----------------------------------------------------

        self.wifi_available = False

        self.wifi_signature = []

        self.wifi_confidence = 0.0

        self.last_wifi_scan = 0

        self.wifi_scan_interval = 10000

        # ----------------------------------------------------
        # BLE LOCALIZATION
        # ----------------------------------------------------

        self.ble_available = False

        self.ble_beacon_detected = False

        self.ble_rssi = None

        self.ble_confidence = 0.0

        self.last_ble_scan = 0

        self.ble_scan_interval = 3000

        # ----------------------------------------------------
        # GPS LOCALIZATION
        # ----------------------------------------------------

        self.gps_available = False

        self.gps_position = None

        self.gps_confidence = 0.0

        # ----------------------------------------------------
        # FUSION STATE
        # ----------------------------------------------------

        self.localization_confidence = 0.0

        self.active_source = SOURCE_NONE

        # ----------------------------------------------------
        # UPDATE TIMERS
        # ----------------------------------------------------

        self.last_update = 0

        self.last_odometry_update = 0

        self.last_imu_update = 0

        # ----------------------------------------------------
        # LOAD PERSISTED HOME
        # ----------------------------------------------------

        self.load_home()

        print("[LOCALIZATION] Spatial awareness ready")

    # ========================================================
    # CONFIG ACCESS
    # ========================================================

    def _get_config(
        self,
        key,
        default
    ):

        if self.config is None:
            return default

        try:

            if isinstance(
                self.config,
                dict
            ):

                return self.config.get(
                    key,
                    default
                )

            return getattr(
                self.config,
                key,
                default
            )

        except Exception:

            return default

    # ========================================================
    # ANGLE NORMALIZATION
    # ========================================================

    def normalize_angle(
        self,
        angle
    ):

        while angle > 180:

            angle -= 360

        while angle < -180:

            angle += 360

        return angle

    # ========================================================
    # POSITION COPY
    # ========================================================

    def _copy_position(
        self,
        position
    ):

        if position is None:
            return None

        return {

            "x": float(
                position.get("x", 0.0)
            ),

            "y": float(
                position.get("y", 0.0)
            ),

            "heading": float(
                position.get("heading", 0.0)
            ),

            "timestamp": position.get(
                "timestamp",
                time.ticks_ms()
            ),

            "source": position.get(
                "source",
                SOURCE_NONE
            ),

            "confidence": float(
                position.get(
                    "confidence",
                    0.0
                )
            )

        }

    # ========================================================
    # ENCODER ACCESS
    # ========================================================

    def _get_encoders(self):

        if not self.drivers:
            return None

        try:

            getter = getattr(
                self.drivers,
                "get_all_encoders",
                None
            )

            if not callable(getter):
                return None

            encoders = getter()

            if not isinstance(
                encoders,
                dict
            ):
                return None

            return encoders

        except Exception:

            return None

    # ========================================================
    # ODOMETRY UPDATE
    # ========================================================

    def update_odometry(self):
        """
        Update local XY position using wheel encoders.

        Current implementation provides a generic omni-drive
        approximation.

        IMPORTANT:

        meters_per_tick must be physically calibrated for
        SATURDAY's actual motors and encoders.

        """

        encoders = self._get_encoders()

        if encoders is None:

            self.encoder_confidence *= 0.95

            return False

        # ----------------------------------------------------
        # FIRST SAMPLE
        # ----------------------------------------------------

        if not self.encoder_initialized:

            self.last_encoders = encoders.copy()

            self.encoder_initialized = True

            self.encoder_confidence = 0.5

            return True

        keys = [

            "CH1_REAR_LEFT",

            "CH2_REAR_RIGHT",

            "CH3_FRONT_LEFT",

            "CH4_FRONT_RIGHT"

        ]

        deltas = {}

        try:

            for key in keys:

                current = encoders.get(
                    key,
                    0
                )

                previous = self.last_encoders.get(
                    key,
                    current
                )

                deltas[key] = current - previous

        except Exception:

            return False

        self.last_encoders = encoders.copy()

        # ----------------------------------------------------
        # OMNI DRIVE MOTION APPROXIMATION
        #
        # Forward component:
        #
        #     FL + FR + RL + RR
        #
        # Lateral component:
        #
        #     -FL + FR + RL - RR
        #
        # This is intentionally isolated here so the exact
        # wheel kinematics can later be calibrated without
        # changing autonomy.
        # ----------------------------------------------------

        rear_left = deltas.get(
            "CH1_REAR_LEFT",
            0
        )

        rear_right = deltas.get(
            "CH2_REAR_RIGHT",
            0
        )

        front_left = deltas.get(
            "CH3_FRONT_LEFT",
            0
        )

        front_right = deltas.get(
            "CH4_FRONT_RIGHT",
            0
        )

        forward_ticks = (

            front_left
            + front_right
            + rear_left
            + rear_right

        ) / 4.0

        lateral_ticks = (

            -front_left
            + front_right
            + rear_left
            - rear_right

        ) / 4.0

        forward_distance = (

            forward_ticks
            * self.meters_per_tick

        )

        lateral_distance = (

            lateral_ticks
            * self.meters_per_tick

        )

        # ----------------------------------------------------
        # ROBOT FRAME -> WORLD FRAME
        # ----------------------------------------------------

        heading_rad = math.radians(

            self.position[
                "heading"
            ]

        )

        world_x = (

            forward_distance
            * math.sin(heading_rad)

            +

            lateral_distance
            * math.cos(heading_rad)

        )

        world_y = (

            forward_distance
            * math.cos(heading_rad)

            -

            lateral_distance
            * math.sin(heading_rad)

        )

        self.position["x"] += world_x

        self.position["y"] += world_y

        self.position["timestamp"] = (
            time.ticks_ms()
        )

        self.position["source"] = (
            SOURCE_ODOMETRY
        )

        # ----------------------------------------------------
        # CONFIDENCE DECAY
        #
        # Dead-reckoning becomes less trustworthy over time.
        # ----------------------------------------------------

        self.encoder_confidence = max(

            0.2,

            min(
                0.85,
                self.encoder_confidence + 0.01
            )

        )

        return True

    # ========================================================
    # IMU ACCESS
    # ========================================================

    def _get_heading(self):

        if not self.drivers:
            return None

        try:

            getter = getattr(

                self.drivers,

                "get_heading",

                None

            )

            if not callable(getter):
                return None

            heading = getter()

            if heading is None:
                return None

            return float(heading)

        except Exception:

            return None

    # ========================================================
    # IMU UPDATE
    # ========================================================

    def update_imu(self):

        heading = self._get_heading()

        if heading is None:

            self.imu_available = False

            self.imu_confidence *= 0.95

            return False

        self.imu_available = True

        self.last_heading = heading

        self.position["heading"] = (
            self.normalize_angle(
                heading
            )
        )

        self.position["timestamp"] = (
            time.ticks_ms()
        )

        self.imu_confidence = min(

            0.95,

            self.imu_confidence + 0.05

        )

        return True

    # ========================================================
    # WIFI SCAN
    # ========================================================

    def _scan_wifi(self):
        """
        Hardware hook for Wi-Fi environment scanning.

        drivers.py may expose:

            scan_wifi()

        Expected output:

        [
            {
                "ssid": "...",
                "bssid": "...",
                "rssi": -55
            }
        ]

        """

        if not self.drivers:
            return None

        try:

            scanner = getattr(

                self.drivers,

                "scan_wifi",

                None

            )

            if not callable(scanner):
                return None

            networks = scanner()

            if not isinstance(
                networks,
                list
            ):
                return None

            return networks

        except Exception:

            return None

    # ========================================================
    # WIFI FINGERPRINT NORMALIZATION
    # ========================================================

    def _normalize_wifi_networks(
        self,
        networks
    ):

        signature = []

        if not networks:
            return signature

        for network in networks:

            try:

                if not isinstance(
                    network,
                    dict
                ):
                    continue

                bssid = network.get(
                    "bssid"
                )

                rssi = network.get(
                    "rssi"
                )

                if bssid is None:
                    continue

                signature.append({

                    "bssid": str(bssid),

                    "rssi": int(rssi)
                    if rssi is not None
                    else -100

                })

            except Exception:

                pass

        return signature

    # ========================================================
    # WIFI SIGNATURE COMPARISON
    # ========================================================

    def _compare_wifi_signatures(
        self,
        current,
        reference
    ):
        """
        Returns similarity from 0.0 to 1.0.

        This is environmental fingerprint matching,
        NOT internet geolocation.

        """

        if not current:
            return 0.0

        if not reference:
            return 0.0

        current_map = {}

        reference_map = {}

        for item in current:

            current_map[
                item["bssid"]
            ] = item.get(
                "rssi",
                -100
            )

        for item in reference:

            reference_map[
                item["bssid"]
            ] = item.get(
                "rssi",
                -100
            )

        matches = 0

        score = 0.0

        for bssid in current_map:

            if bssid in reference_map:

                matches += 1

                difference = abs(

                    current_map[bssid]
                    - reference_map[bssid]

                )

                strength_score = max(

                    0.0,

                    1.0
                    - (
                        difference / 50.0
                    )

                )

                score += strength_score

        if matches == 0:
            return 0.0

        overlap = matches / max(

            len(current_map),

            len(reference_map)

        )

        strength = score / matches

        return (

            overlap * 0.6
            + strength * 0.4

        )

    # ========================================================
    # WIFI UPDATE
    # ========================================================

    def update_wifi(self):

        now = time.ticks_ms()

        if time.ticks_diff(

            now,

            self.last_wifi_scan

        ) < self.wifi_scan_interval:

            return False

        self.last_wifi_scan = now

        networks = self._scan_wifi()

        if networks is None:

            self.wifi_available = False

            self.wifi_confidence *= 0.9

            return False

        self.wifi_available = True

        self.wifi_signature = (

            self._normalize_wifi_networks(
                networks
            )

        )

        if self.home_initialized:

            similarity = (

                self._compare_wifi_signatures(

                    self.wifi_signature,

                    self.home.get(
                        "wifi_signature",
                        []
                    )

                )

            )

            self.wifi_confidence = similarity

        return True

    # ========================================================
    # BLE SCAN
    # ========================================================

    def _scan_ble(self):
        """
        Hook for dock BLE beacon detection.

        drivers.py may expose:

            scan_ble()

        Expected result:

        [
            {
                "name": "SATURDAY_DOCK",
                "address": "...",
                "rssi": -45
            }
        ]

        """

        if not self.drivers:
            return None

        try:

            scanner = getattr(

                self.drivers,

                "scan_ble",

                None

            )

            if not callable(scanner):
                return None

            devices = scanner()

            if not isinstance(
                devices,
                list
            ):
                return None

            return devices

        except Exception:

            return None

    # ========================================================
    # BLE UPDATE
    # ========================================================

    def update_ble(self):

        if not self.home_initialized:

            return False

        beacon = self.home.get(
            "ble_beacon"
        )

        if not beacon:

            return False

        now = time.ticks_ms()

        if time.ticks_diff(

            now,

            self.last_ble_scan

        ) < self.ble_scan_interval:

            return False

        self.last_ble_scan = now

        devices = self._scan_ble()

        if devices is None:

            self.ble_available = False

            self.ble_beacon_detected = False

            self.ble_confidence = 0.0

            return False

        self.ble_available = True

        target_address = beacon.get(
            "address"
        )

        target_name = beacon.get(
            "name"
        )

        for device in devices:

            try:

                address = device.get(
                    "address"
                )

                name = device.get(
                    "name"
                )

                if (

                    (
                        target_address
                        and address == target_address
                    )

                    or

                    (
                        target_name
                        and name == target_name
                    )

                ):

                    self.ble_beacon_detected = True

                    self.ble_rssi = device.get(
                        "rssi"
                    )

                    rssi = self.ble_rssi

                    if rssi is not None:

                        # RSSI confidence approximation.

                        confidence = (

                            float(rssi)
                            + 100

                        ) / 60.0

                        self.ble_confidence = max(

                            0.0,

                            min(
                                1.0,
                                confidence
                            )

                        )

                    return True

            except Exception:

                pass

        self.ble_beacon_detected = False

        self.ble_confidence = 0.0

        return False

    # ========================================================
    # GPS UPDATE HOOK
    # ========================================================

    def update_gps(self):
        """
        Optional outdoor localization.

        drivers.py may expose:

            get_gps()

        Expected:

        {
            "latitude": ...,
            "longitude": ...,
            "accuracy": ...
        }

        """

        if not self.drivers:
            return False

        try:

            getter = getattr(

                self.drivers,

                "get_gps",

                None

            )

            if not callable(getter):
                return False

            gps = getter()

            if not isinstance(
                gps,
                dict
            ):
                return False

            latitude = gps.get(
                "latitude"
            )

            longitude = gps.get(
                "longitude"
            )

            if (
                latitude is None
                or longitude is None
            ):

                return False

            self.gps_position = {

                "latitude": float(
                    latitude
                ),

                "longitude": float(
                    longitude
                ),

                "accuracy": gps.get(
                    "accuracy",
                    None
                ),

                "timestamp": time.ticks_ms()

            }

            self.gps_available = True

            accuracy = gps.get(
                "accuracy"
            )

            if accuracy is not None:

                try:

                    self.gps_confidence = max(

                        0.0,

                        min(

                            1.0,

                            1.0
                            - (
                                float(accuracy)
                                / 50.0
                            )

                        )

                    )

                except Exception:

                    self.gps_confidence = 0.5

            else:

                self.gps_confidence = 0.5

            return True

        except Exception:

            self.gps_available = False

            return False

    # ========================================================
    # CAPTURE HOME
    # ========================================================

    def set_home(
        self,
        capture_wifi=True,
        ble_beacon=None
    ):
        """
        Capture SATURDAY's CURRENT physical position as home.

        This should normally happen when SATURDAY starts from
        its dock/base.

        The home location stores:

        - local XY coordinate
        - heading
        - Wi-Fi environmental fingerprint
        - optional BLE beacon identity
        - optional GPS coordinate

        """

        now = time.ticks_ms()

        if capture_wifi:

            self.update_wifi()

        self.home = {

            "x": float(
                self.position["x"]
            ),

            "y": float(
                self.position["y"]
            ),

            "heading": float(
                self.position["heading"]
            ),

            "timestamp": now,

            "wifi_signature": list(
                self.wifi_signature
            ),

            "ble_beacon": ble_beacon,

            "gps": self.gps_position,

            "confidence": self.localization_confidence

        }

        self.home_initialized = True

        self.save_home()

        print(
            "[LOCALIZATION] Home captured:",
            self.home
        )

        return True

    # ========================================================
    # SET EXPLICIT HOME
    # ========================================================

    def set_home_position(
        self,
        position
    ):

        if not isinstance(
            position,
            dict
        ):
            return False

        self.home["x"] = float(
            position.get(
                "x",
                0.0
            )
        )

        self.home["y"] = float(
            position.get(
                "y",
                0.0
            )
        )

        self.home["heading"] = float(
            position.get(
                "heading",
                0.0
            )
        )

        self.home["timestamp"] = (
            time.ticks_ms()
        )

        self.home_initialized = True

        self.save_home()

        return True

    # ========================================================
    # PERSIST HOME
    # ========================================================

    def save_home(self):

        if json is None:
            return False

        try:

            with open(
                self.home_file,
                "w"
            ) as file:

                json.dump(
                    self.home,
                    file
                )

            return True

        except Exception as e:

            print(
                "[LOCALIZATION] Home save failed:",
                e
            )

            return False

    # ========================================================
    # LOAD HOME
    # ========================================================

    def load_home(self):

        if json is None:
            return False

        try:

            with open(
                self.home_file,
                "r"
            ) as file:

                data = json.load(
                    file
                )

            if isinstance(
                data,
                dict
            ):

                self.home.update(
                    data
                )

                self.home_initialized = True

                print(
                    "[LOCALIZATION] Persistent home restored"
                )

                return True

        except Exception:

            pass

        return False

    # ========================================================
    # CLEAR HOME
    # ========================================================

    def clear_home(self):

        self.home_initialized = False

        self.home = {

            "x": 0.0,

            "y": 0.0,

            "heading": 0.0,

            "timestamp": 0,

            "wifi_signature": [],

            "ble_beacon": None,

            "gps": None,

            "confidence": 0.0

        }

        try:

            if os:

                os.remove(
                    self.home_file
                )

        except Exception:

            pass

        return True

    # ========================================================
    # DISTANCE TO POSITION
    # ========================================================

    def distance_to(
        self,
        target
    ):

        if not isinstance(
            target,
            dict
        ):
            return None

        try:

            dx = (

                float(target["x"])
                - self.position["x"]

            )

            dy = (

                float(target["y"])
                - self.position["y"]

            )

            return math.sqrt(

                dx * dx
                + dy * dy

            )

        except Exception:

            return None

    # ========================================================
    # BEARING TO POSITION
    # ========================================================

    def bearing_to(
        self,
        target
    ):

        if not isinstance(
            target,
            dict
        ):
            return None

        try:

            dx = (

                float(target["x"])
                - self.position["x"]

            )

            dy = (

                float(target["y"])
                - self.position["y"]

            )

            return math.degrees(

                math.atan2(
                    dx,
                    dy
                )

            )

        except Exception:

            return None

    # ========================================================
    # DISTANCE TO HOME
    # ========================================================

    def distance_to_home(self):

        if not self.home_initialized:
            return None

        return self.distance_to(
            self.home
        )

    # ========================================================
    # BEARING TO HOME
    # ========================================================

    def bearing_to_home(self):

        if not self.home_initialized:
            return None

        return self.bearing_to(
            self.home
        )

    # ========================================================
    # HEADING ERROR
    # ========================================================

    def heading_error_to(
        self,
        target
    ):

        bearing = self.bearing_to(
            target
        )

        if bearing is None:
            return None

        return self.normalize_angle(

            bearing
            - self.position["heading"]

        )

    # ========================================================
    # HOME ZONE CHECK
    # ========================================================

    def is_near_home(
        self,
        radius=None
    ):

        if radius is None:

            radius = self.home_zone_radius

        distance = self.distance_to_home()

        if distance is None:
            return False

        return distance <= radius

    # ========================================================
    # WIFI HOME DETECTION
    # ========================================================

    def wifi_home_detected(
        self,
        threshold=0.65
    ):

        if not self.home_initialized:
            return False

        similarity = (

            self._compare_wifi_signatures(

                self.wifi_signature,

                self.home.get(
                    "wifi_signature",
                    []
                )

            )

        )

        return similarity >= threshold

    # ========================================================
    # BLE HOME DETECTION
    # ========================================================

    def ble_home_detected(
        self,
        minimum_confidence=0.35
    ):

        return (

            self.ble_beacon_detected

            and

            self.ble_confidence
            >= minimum_confidence

        )

    # ========================================================
    # FUSION
    # ========================================================

    def update_fusion(self):
        """
        Determine localization confidence and active source.

        This is deliberately lightweight for ESP32.

        It does not pretend to be a Kalman filter.

        A future upgrade can replace this method with EKF
        without changing the public API.
        """

        scores = []

        # Encoder + IMU fusion is primary local positioning.

        if self.encoder_initialized:

            encoder_score = (
                self.encoder_confidence
            )

            if self.imu_available:

                encoder_score = min(

                    1.0,

                    encoder_score
                    * 0.7

                    +

                    self.imu_confidence
                    * 0.3

                )

                self.active_source = SOURCE_FUSED

            else:

                self.active_source = (
                    SOURCE_ODOMETRY
                )

            scores.append(
                encoder_score
            )

        # GPS can dominate outdoors.

        if self.gps_available:

            scores.append(
                self.gps_confidence
            )

            if (
                self.gps_confidence
                > self.localization_confidence
            ):

                self.active_source = SOURCE_GPS

        # BLE strongly confirms proximity to home.

        if self.ble_beacon_detected:

            scores.append(
                self.ble_confidence
            )

        # Wi-Fi confirms environmental context.

        if self.wifi_available:

            scores.append(
                self.wifi_confidence
            )

        if scores:

            self.localization_confidence = min(

                1.0,

                max(scores)

            )

        else:

            self.localization_confidence = 0.0

            self.active_source = SOURCE_NONE

        self.position["confidence"] = (
            self.localization_confidence
        )

        self.position["source"] = (
            self.active_source
        )

        # Preserve useful position.

        if self.localization_confidence >= 0.4:

            self.last_known_position = (
                self._copy_position(
                    self.position
                )
            )

    # ========================================================
    # MAIN UPDATE
    # ========================================================

    def update(self):
        """
        Non-blocking localization update.

        Intended to be called continuously by Runtime.
        """

        self.update_odometry()

        self.update_imu()

        self.update_wifi()

        self.update_ble()

        self.update_gps()

        self.update_fusion()

        self.last_update = (
            time.ticks_ms()
        )

        return self.get_position()

    # ========================================================
    # POSITION ACCESS
    # ========================================================

    def get_position(self):

        return self._copy_position(
            self.position
        )

    # ========================================================
    # HOME ACCESS
    # ========================================================

    def get_home(self):

        if not self.home_initialized:
            return None

        return dict(
            self.home
        )

    # ========================================================
    # LOCALIZATION HEALTH
    # ========================================================

    def is_healthy(
        self,
        minimum_confidence=0.3
    ):

        return (

            self.localization_confidence
            >= minimum_confidence

        )

    # ========================================================
    # HOME CONFIDENCE
    # ========================================================

    def home_confidence(self):
        """
        Confidence that SATURDAY is currently near the
        remembered home environment.
        """

        scores = []

        # Geometric position.

        distance = self.distance_to_home()

        if distance is not None:

            if distance <= self.home_zone_radius:

                scores.append(1.0)

            else:

                geometric = max(

                    0.0,

                    1.0
                    - (
                        distance
                        / 10.0
                    )

                )

                scores.append(
                    geometric
                )

        # Wi-Fi fingerprint.

        if self.wifi_available:

            similarity = (

                self._compare_wifi_signatures(

                    self.wifi_signature,

                    self.home.get(
                        "wifi_signature",
                        []
                    )

                )

            )

            scores.append(
                similarity
            )

        # BLE beacon.

        if self.ble_beacon_detected:

            scores.append(
                self.ble_confidence
            )

        if not scores:
            return 0.0

        return sum(scores) / len(scores)

    # ========================================================
    # GPS DISTANCE
    # ========================================================

    def gps_distance_to_home(self):
        """
        Haversine distance in meters.

        Only useful when both current GPS and home GPS exist.
        """

        if not self.gps_position:
            return None

        home_gps = self.home.get(
            "gps"
        )

        if not home_gps:
            return None

        try:

            lat1 = math.radians(

                float(
                    self.gps_position[
                        "latitude"
                    ]
                )

            )

            lon1 = math.radians(

                float(
                    self.gps_position[
                        "longitude"
                    ]
                )

            )

            lat2 = math.radians(

                float(
                    home_gps[
                        "latitude"
                    ]
                )

            )

            lon2 = math.radians(

                float(
                    home_gps[
                        "longitude"
                    ]
                )

            )

            dlat = lat2 - lat1

            dlon = lon2 - lon1

            a = (

                math.sin(
                    dlat / 2
                ) ** 2

                +

                math.cos(lat1)

                *

                math.cos(lat2)

                *

                math.sin(
                    dlon / 2
                ) ** 2

            )

            c = (

                2
                * math.atan2(

                    math.sqrt(a),

                    math.sqrt(
                        1 - a
                    )

                )

            )

            earth_radius = 6371000

            return (
                earth_radius * c
            )

        except Exception:

            return None

    # ========================================================
    # STATUS
    # ========================================================

    def status(self):

        return {

            "position":
                self.get_position(),

            "home":
                self.get_home(),

            "home_initialized":
                self.home_initialized,

            "distance_to_home":
                self.distance_to_home(),

            "bearing_to_home":
                self.bearing_to_home(),

            "gps_distance_to_home":
                self.gps_distance_to_home(),

            "home_confidence":
                self.home_confidence(),

            "localization_confidence":
                self.localization_confidence,

            "active_source":
                self.active_source,

            "encoder": {

                "initialized":
                    self.encoder_initialized,

                "confidence":
                    self.encoder_confidence

            },

            "imu": {

                "available":
                    self.imu_available,

                "confidence":
                    self.imu_confidence

            },

            "wifi": {

                "available":
                    self.wifi_available,

                "confidence":
                    self.wifi_confidence,

                "home_detected":
                    self.wifi_home_detected()

            },

            "ble": {

                "available":
                    self.ble_available,

                "detected":
                    self.ble_beacon_detected,

                "rssi":
                    self.ble_rssi,

                "confidence":
                    self.ble_confidence

            },

            "gps": {

                "available":
                    self.gps_available,

                "position":
                    self.gps_position,

                "confidence":
                    self.gps_confidence

            },

            "last_known_position":
                self.last_known_position

        }

    # ========================================================
    # MEMORY MAINTENANCE
    # ========================================================

    def cleanup(self):

        try:

            gc.collect()

        except Exception:

            pass


# ============================================================
# COMPATIBILITY ALIASES
# ============================================================

LocalizationEngine = Localization

SaturdayLocalization = Localization

SATURDAYLocalization = Localization