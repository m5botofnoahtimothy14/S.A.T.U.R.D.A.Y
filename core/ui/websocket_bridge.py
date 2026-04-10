                        
import logging
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import threading

logger = logging.getLogger("AEGIS.UI.Bridge")

class WebSocketBridge:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.app = Flask(__name__, template_folder="dashboard", static_folder="dashboard")
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        self.event_bus.subscribe("security_alert", self._on_security_alert)
        self.event_bus.subscribe("homebot_telemetry", self._on_telemetry)
        self.event_bus.subscribe("voice_response", self._on_voice)
        self.event_bus.subscribe("scripture_update", self._on_scripture)
        self.event_bus.subscribe("health_update", self._on_health)

        @self.app.route('/')
        def index():
            return render_template("index.html")

        @self.socketio.on('connect')
        def handle_connect():
            logger.info("UI Client connected.")
            emit('system_status', {'status': 'online', 'version': 'alpha-1.0'})

        @self.socketio.on('ui_command')
        def handle_command(data):
            logger.info(f"Command received from UI: {data}")
            self.event_bus.publish("voice_command", data.get("command"))

    def _on_security_alert(self, data):
        self.socketio.emit('security_alert', data)

    def _on_telemetry(self, data):
        self.socketio.emit('homebot_telemetry', data)

    def _on_voice(self, data):
        self.socketio.emit('voice_msg', {'text': data})

    def _on_scripture(self, data):
        self.socketio.emit('scripture_msg', {'text': data})

    def _on_health(self, data):
        self.socketio.emit('health_update', data)

    def start(self, port=5000):
        threading.Thread(target=lambda: self.socketio.run(self.app, port=port, use_reloader=False, log_output=False), daemon=True).start()
        logger.info(f"UI WebSocket Bridge started on port {port}")
