============================================================
SATURDAY COMMUNICATION
MQTT Nervous System Gateway
============================================================

Responsibilities:
- Non-blocking MQTT connectivity
- Primary / secondary broker failover
- Automatic reconnect
- Command reception
- Event publishing
- Telemetry publishing
- Heartbeat
- Message queues

IMPORTANT:
Communication never directly controls hardware.
Runtime remains responsible for decisions and arbitration.
============================================================

import time

try:
    import json
except ImportError:
    json = None


class Communication:

    def __init__(self, config=None):

        print("[COMMS] Initializing communication layer...")

        self.config = config

        # ====================================================
        # CONNECTION STATE
        # ====================================================

        self.connected = False
        self.connecting = False

        self.last_connect_attempt = 0

        self.reconnect_interval = 5000

        self.last_heartbeat = 0
        self.heartbeat_interval = 10000

        self.last_telemetry = 0
        self.telemetry_interval = 3000

        # ====================================================
        # MQTT CLIENT
        # ====================================================

        self.client = None
        self.MQTTClient = None

        self.mqtt_available = False

        # ====================================================
        # BROKER STATE
        # ====================================================

        self.primary_broker = None
        self.secondary_broker = None

        self.current_broker = None

        self.last_successful_broker = None

        self.broker_toggle = False

        # ====================================================
        # MESSAGE QUEUES
        # ====================================================

        self.incoming = []
        self.outgoing = []

        self.max_queue = 30

        # ====================================================
        # DEVICE / TOPICS
        # ====================================================

        self.device_id = "saturday_homebot_01"

        self.topic_prefix = "saturday"

        self.command_topic = None
        self.event_topic = None
        self.status_topic = None
        self.telemetry_topic = None
        self.heartbeat_topic = None
        self.intent_topic = None
        self.voice_topic = None

        # ====================================================
        # LOAD CONFIGURATION
        # ====================================================

        self._load_config()

        print("[COMMS] Communication layer ready")
        print("[COMMS] Primary broker:", self.primary_broker)

    # ========================================================
    # CONFIG LOADING
    # ========================================================

    def _load_config(self):

        if not self.config:

            print("[COMMS] No config supplied")

            return

        try:

            # ------------------------------------------------
            # DEVICE ID
            # ------------------------------------------------

            self.device_id = getattr(
                self.config,
                "DEVICE_ID",
                self.device_id
            )

            # ------------------------------------------------
            # MQTT ROOT
            # ------------------------------------------------

            self.topic_prefix = getattr(
                self.config,
                "MQTT_ROOT",
                self.topic_prefix
            )

            # ------------------------------------------------
            # BROKERS
            # ------------------------------------------------

            self.primary_broker = getattr(
                self.config,
                "MQTT_PRIMARY",
                "192.168.1.38"
            )

            self.secondary_broker = getattr(
                self.config,
                "MQTT_SECONDARY",
                self.primary_broker
            )

            # ------------------------------------------------
            # TIMING
            # ------------------------------------------------

            self.reconnect_interval = getattr(
                self.config,
                "MQTT_RECONNECT_MS",
                self.reconnect_interval
            )

            # ------------------------------------------------
            # TOPICS
            #
            # Prefer explicitly configured topics.
            # Otherwise generate them from MQTT_ROOT + DEVICE_ID.
            # ------------------------------------------------

            base = (
                self.topic_prefix +
                "/" +
                self.device_id
            )

            self.command_topic = getattr(
                self.config,
                "MQTT_TOPIC_COMMAND",
                base + "/command"
            )

            self.event_topic = getattr(
                self.config,
                "MQTT_TOPIC_EVENTS",
                base + "/events"
            )

            self.status_topic = getattr(
                self.config,
                "MQTT_TOPIC_STATUS",
                base + "/status"
            )

            self.telemetry_topic = getattr(
                self.config,
                "MQTT_TOPIC_TELEMETRY",
                base + "/telemetry"
            )

            self.intent_topic = getattr(
                self.config,
                "MQTT_TOPIC_INTENT",
                base + "/intent"
            )

            self.voice_topic = getattr(
                self.config,
                "MQTT_TOPIC_VOICE",
                base + "/voice"
            )

            self.heartbeat_topic = (
                base + "/heartbeat"
            )

            print(
                "[COMMS] Config loaded successfully"
            )

        except Exception as e:

            print(
                "[COMMS] Config loading warning:",
                e
            )

    # ========================================================
    # MQTT INITIALIZATION
    # ========================================================

    def initialize(self):

        print("[COMMS] Preparing MQTT...")

        try:

            from umqtt.simple import MQTTClient

            self.MQTTClient = MQTTClient

            self.mqtt_available = True

            print("[COMMS] MQTT library available")

            return True

        except Exception as e:

            self.mqtt_available = False

            print(
                "[COMMS] MQTT unavailable:",
                e
            )

            return False

    # ========================================================
    # GET CONFIG
    # ========================================================

    def _get_config(self, name, default=None):

        try:

            if self.config:

                return getattr(
                    self.config,
                    name,
                    default
                )

        except Exception:
            pass

        return default

    # ========================================================
    # BROKER SELECTION
    # ========================================================

    def _select_broker(self):

        # Prefer previously successful broker.

        if self.last_successful_broker:

            return self.last_successful_broker

        # Alternate primary / secondary.

        if not self.broker_toggle:

            self.broker_toggle = True

            return self.primary_broker

        self.broker_toggle = False

        return self.secondary_broker

    # ========================================================
    # MQTT CALLBACK
    # ========================================================

    def _on_message(self, topic, message):

        try:

            if isinstance(topic, bytes):

                topic = topic.decode()

            if isinstance(message, bytes):

                message = message.decode()

            payload = self._decode(
                message
            )

            event = {

                "topic": topic,

                "payload": payload,

                "timestamp": time.ticks_ms()

            }

            self._push_incoming(
                event
            )

        except Exception as e:

            print(
                "[COMMS] Message error:",
                e
            )

    # ========================================================
    # DECODE
    # ========================================================

    def _decode(self, message):

        if not isinstance(
            message,
            str
        ):

            return message

        if json:

            try:

                return json.loads(
                    message
                )

            except Exception:

                pass

        return {

            "type": "raw",

            "data": message

        }

    # ========================================================
    # ENCODE
    # ========================================================

    def _encode(self, payload):

        if isinstance(
            payload,
            str
        ):

            return payload

        if json:

            try:

                return json.dumps(
                    payload
                )

            except Exception:

                pass

        return str(
            payload
        )

    # ========================================================
    # QUEUE MANAGEMENT
    # ========================================================

    def _push_incoming(self, event):

        if len(
            self.incoming
        ) >= self.max_queue:

            self.incoming.pop(0)

        self.incoming.append(
            event
        )

    def _push_outgoing(self, event):

        if len(
            self.outgoing
        ) >= self.max_queue:

            self.outgoing.pop(0)

        self.outgoing.append(
            event
        )

    # ========================================================
    # CONNECT
    # ========================================================

    def connect(self):

        if not self.mqtt_available:

            return False

        if self.connected:

            return True

        now = time.ticks_ms()

        elapsed = time.ticks_diff(
            now,
            self.last_connect_attempt
        )

        if elapsed < self.reconnect_interval:

            return False

        self.last_connect_attempt = now

        broker = self._select_broker()

        port = self._get_config(
            "MQTT_PORT",
            1883
        )

        client_id = self._get_config(
            "DEVICE_ID",
            "saturday_homebot_01"
        )

        username = self._get_config(
            "MQTT_USER",
            ""
        )

        password = self._get_config(
            "MQTT_PASSWORD",
            ""
        )

        keepalive = self._get_config(
            "MQTT_KEEPALIVE",
            30
        )

        if not broker:

            print(
                "[COMMS] No MQTT broker configured"
            )

            return False

        try:

            print(
                "[COMMS] Connecting MQTT:",
                broker
            )

            # --------------------------------------------
            # CREATE CLIENT
            # --------------------------------------------

            if username:

                self.client = self.MQTTClient(

                    client_id,

                    broker,

                    port=port,

                    user=username,

                    password=password,

                    keepalive=keepalive

                )

            else:

                self.client = self.MQTTClient(

                    client_id,

                    broker,

                    port=port,

                    keepalive=keepalive

                )

            # --------------------------------------------
            # CALLBACK
            # --------------------------------------------

            self.client.set_callback(
                self._on_message
            )

            # --------------------------------------------
            # CONNECT
            # --------------------------------------------

            self.client.connect()

            # --------------------------------------------
            # SUBSCRIBE
            # --------------------------------------------

            self.client.subscribe(
                self.command_topic
            )

            self.client.subscribe(
                self.intent_topic
            )

            self.client.subscribe(
                self.voice_topic
            )

            # --------------------------------------------
            # SUCCESS
            # --------------------------------------------

            self.connected = True

            self.connecting = False

            self.current_broker = broker

            self.last_successful_broker = broker

            print(
                "[COMMS] MQTT CONNECTED"
            )

            print(
                "[COMMS] Broker:",
                broker
            )

            print(
                "[COMMS] Command topic:",
                self.command_topic
            )

            self.publish_event({

                "type": "system",

                "event": "online",

                "device": self.device_id

            })

            return True

        except Exception as e:

            print(
                "[COMMS] MQTT connection failed:",
                e
            )

            self.connected = False

            self.connecting = False

            self.client = None

            # If preferred broker fails,
            # allow the alternate broker next time.

            if broker == self.last_successful_broker:

                self.last_successful_broker = None

            return False

    # ========================================================
    # DISCONNECT
    # ========================================================

    def disconnect(self):

        try:

            if self.client:

                self.client.disconnect()

        except Exception:

            pass

        self.client = None

        self.connected = False

        self.current_broker = None

        print(
            "[COMMS] MQTT disconnected"
        )

    # ========================================================
    # PUBLISH
    # ========================================================

    def publish(self, topic, payload):

        event = {

            "topic": topic,

            "payload": payload

        }

        self._push_outgoing(
            event
        )

        return True

    # ========================================================
    # INTERNAL SEND
    # ========================================================

    def _send(self, topic, payload):

        if not self.connected:

            return False

        if not self.client:

            return False

        try:

            data = self._encode(
                payload
            )

            self.client.publish(
                topic,
                data
            )

            return True

        except Exception as e:

            print(
                "[COMMS] Publish error:",
                e
            )

            self.connected = False

            self.client = None

            return False

    # ========================================================
    # EVENTS
    # ========================================================

    def publish_event(self, event):

        return self.publish(
            self.event_topic,
            event
        )

    # ========================================================
    # STATUS
    # ========================================================

    def publish_status(self, status):

        return self.publish(
            self.status_topic,
            status
        )

    # ========================================================
    # TELEMETRY
    # ========================================================

    def publish_telemetry(self, telemetry):

        return self.publish(
            self.telemetry_topic,
            telemetry
        )

    # ========================================================
    # HEARTBEAT
    # ========================================================

    def heartbeat(self):

        now = time.ticks_ms()

        elapsed = time.ticks_diff(
            now,
            self.last_heartbeat
        )

        if elapsed < self.heartbeat_interval:

            return

        self.last_heartbeat = now

        self.publish(

            self.heartbeat_topic,

            {

                "type": "heartbeat",

                "online": True,

                "device": self.device_id,

                "timestamp": now

            }

        )

    # ========================================================
    # MQTT POLL
    # ========================================================

    def poll(self):

        if not self.connected:

            return False

        if not self.client:

            return False

        try:

            self.client.check_msg()

            return True

        except Exception as e:

            print(
                "[COMMS] MQTT poll error:",
                e
            )

            self.connected = False

            self.client = None

            return False

    # ========================================================
    # FLUSH OUTGOING
    # ========================================================

    def flush(self):

        if not self.connected:

            return

        if not self.outgoing:

            return

        limit = 3

        sent = 0

        while (

            self.outgoing
            and sent < limit

        ):

            event = self.outgoing.pop(0)

            success = self._send(

                event["topic"],

                event["payload"]

            )

            if not success:

                self.outgoing.insert(
                    0,
                    event
                )

                break

            sent += 1

    # ========================================================
    # GET MESSAGE
    # ========================================================

    def get_message(self):

        if not self.incoming:

            return None

        return self.incoming.pop(0)

    # ========================================================
    # GET COMMAND
    # ========================================================

    def get_command(self):

        while self.incoming:

            event = self.get_message()

            if not event:

                continue

            topic = event.get(
                "topic"
            )

            if topic == self.command_topic:

                return event.get(
                    "payload"
                )

        return None

    # ========================================================
    # GET INTENT
    # ========================================================

    def get_intent(self):

        while self.incoming:

            event = self.get_message()

            if not event:

                continue

            topic = event.get(
                "topic"
            )

            if topic == self.intent_topic:

                return event.get(
                    "payload"
                )

        return None

    # ========================================================
    # GET VOICE
    # ========================================================

    def get_voice(self):

        while self.incoming:

            event = self.get_message()

            if not event:

                continue

            topic = event.get(
                "topic"
            )

            if topic == self.voice_topic:

                return event.get(
                    "payload"
                )

        return None

    # ========================================================
    # TELEMETRY
    # ========================================================

    def update_telemetry(self, data):

        now = time.ticks_ms()

        elapsed = time.ticks_diff(

            now,

            self.last_telemetry

        )

        if elapsed < self.telemetry_interval:

            return

        self.last_telemetry = now

        self.publish_telemetry(
            data
        )

    # ========================================================
    # MAIN UPDATE
    # ========================================================

    def update(self):

        if not self.mqtt_available:

            return

        # ------------------------------------------------
        # CONNECT / RECONNECT
        # ------------------------------------------------

        if not self.connected:

            self.connect()

            return

        # ------------------------------------------------
        # PROCESS ONE MQTT MESSAGE
        # ------------------------------------------------

        self.poll()

        # ------------------------------------------------
        # HEARTBEAT
        # ------------------------------------------------

        self.heartbeat()

        # ------------------------------------------------
        # OUTGOING MESSAGES
        # ------------------------------------------------

        self.flush()

    # ========================================================
    # STATUS
    # ========================================================

    def status(self):

        return {

            "connected": self.connected,

            "mqtt_available": self.mqtt_available,

            "broker": self.current_broker,

            "primary_broker": self.primary_broker,

            "secondary_broker": self.secondary_broker,

            "incoming_queue": len(
                self.incoming
            ),

            "outgoing_queue": len(
                self.outgoing
            ),

            "command_topic": self.command_topic,

            "intent_topic": self.intent_topic,

            "voice_topic": self.voice_topic

        }


# ============================================================
# COMPATIBILITY ALIASES
# ============================================================

CommunicationManager = Communication
MQTTCommunication = Communication