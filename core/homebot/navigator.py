                       
import logging
from sensors.homebot_sensors import HomeBotSensors as Sensors
import math
import time

logger = logging.getLogger("SATURDAY.HomeBot.Navigation")

class Navigation:
    def __init__(self, sensors: Sensors):
        self.sensors = sensors
        self.grid_map = {}                                     
        self.position = (0, 0)                            
        self.orientation = 0                   

    def update_map(self):
                                                           
        distance = self.sensors.read_ultrasonic()
        vibration = self.sensors.read_vibration()
        wifi_map = self.sensors.scan_wifi_heatmap()

        self.grid_map[self.position] = {
            "distance": distance,
            "vibration": vibration,
            "wifi": wifi_map
        }
        logger.info(f"Navigator map updated at {self.position}: {self.grid_map[self.position]}")

    def plan_path(self, target_pos):
        
        logger.info(f"Planning path from {self.position} to {target_pos}")

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
        
        commands = self.plan_path(target_pos)
        for cmd in commands:
            motors.execute_command(cmd)
            self.update_map()
            time.sleep(0.5)                           
