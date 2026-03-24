# homebot/navigation.py
import logging
from sensors.homebot_sensors import HomeBotSensors as Sensors
import math
import time

logger = logging.getLogger("AEGIS.HomeBot.Navigation")

class Navigation:
    def __init__(self, sensors: Sensors):
        self.sensors = sensors
        self.grid_map = {}      # e.g., {(x, y): obstacle/rssi}
        self.position = (0, 0)  # HomeBot real-time coords
        self.orientation = 0    # Degrees 0-359

    def update_map(self):
        # Pull sensor data and WiFi heatmap for IRL mapping
        distance = self.sensors.read_ultrasonic()
        vibration = self.sensors.read_vibration()
        wifi_map = self.sensors.scan_wifi_heatmap()

        # IRL: map position based on sensor + WiFi signals
        self.grid_map[self.position] = {
            "distance": distance,
            "vibration": vibration,
            "wifi": wifi_map
        }
        logger.info(f"Navigator map updated at {self.position}: {self.grid_map[self.position]}")

    def plan_path(self, target_pos):
        """
        IRL: Plan real-time path from current pos to target_pos using sensor + WiFi map.
        Returns list of movement commands (forward, strafe, rotate)
        """
        logger.info(f"Planning path from {self.position} to {target_pos}")

        # For simplicity, generate straight-line steps (replace with A* later)
        dx = target_pos[0] - self.position[0]
        dy = target_pos[1] - self.position[1]
        commands = []

        if dx > 0:
            commands.append("strafe_right")
        elif dx < 0:
            commands.append("strafe_left")

        if dy > 0:
            commands.append("forward")
        elif dy < 0:
            commands.append("backward")

        logger.info(f"Planned path commands: {commands}")
        return commands

    def move_to(self, target_pos, motors):
        """
        IRL: Move HomeBot to target_pos using motors
        """
        commands = self.plan_path(target_pos)
        for cmd in commands:
            motors.execute_command(cmd)
            self.update_map()
            time.sleep(0.5)  # Wait a bit for movement
