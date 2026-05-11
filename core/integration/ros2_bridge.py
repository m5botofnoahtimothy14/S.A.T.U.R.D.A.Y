import asyncio
import structlog

logger = structlog.get_logger("SATURDAY.ROS2")

class ROS2Bridge:
    
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.active = False
        self.node = None
        self.publisher = None
        self.command_subscription = None
        self.speech_topic = "saturday/speech"
        self.command_topic = "saturday/command"
        
        try:
            import rclpy
            from std_msgs.msg import String
            self.rclpy = rclpy
            self.StringMsg = String
            self.active = True
        except ImportError:
            logger.warning("rclpy (ROS2) not found. ROS2 Bridge will be disabled.")
            
        self.event_bus.subscribe("voice_response", self._bridge_to_ros2)
        
        logger.info("ROS2 Bridge initialized.", active=self.active)

    def _bridge_to_ros2(self, text: str):
        
        if not self.active or not self.node: return
        
        try:
            msg = self.StringMsg()
            msg.data = text
            if self.publisher:
                self.publisher.publish(msg)
        except Exception as e:
            logger.error("Failed to publish to ROS2", error=str(e))

    def _on_ros2_command(self, msg):
        
        command_text = msg.data
        logger.info("Received ROS2 command", command=command_text)
        self.event_bus.publish("text_command", command_text)

    async def start(self):
        
        if not self.active: return
        
        try:
            if not self.rclpy.ok():
                self.rclpy.init()
                
            self.node = self.rclpy.create_node('saturday_os_bridge')
            
            self.publisher = self.node.create_publisher(self.StringMsg, self.speech_topic, 10)
            self.command_subscription = self.node.create_subscription(
                self.StringMsg,
                self.command_topic,
                self._on_ros2_command,
                10,
            )
            
            logger.info("ROS2 Node 'saturday_os_bridge' started.")
            
            while self.rclpy.ok():
                self.rclpy.spin_once(self.node, timeout_sec=0.01)
                await asyncio.sleep(0.01)
        except Exception as e:
            logger.error("ROS2 execution error", error=str(e))
            self.active = False
