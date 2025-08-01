#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class ChatterPublisher(Node):

    def __init__(self):
        super().__init__("chatter_publisher")
        self.publisher_ = self.create_publisher(String, "/chatter", 10)
        timer_period = 1.0  # seconds
        self.timer = self.create_timer(timer_period, self.timer_callback)
        self.count = 0

        self.get_logger().info("Chatter publisher started")

    def timer_callback(self):
        msg = String()
        msg.data = f"Hello World: {self.count}"
        self.publisher_.publish(msg)
        self.get_logger().info(f'Publishing: "{msg.data}"')
        self.count += 1


def main(args=None):
    rclpy.init(args=args)

    node = ChatterPublisher()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
