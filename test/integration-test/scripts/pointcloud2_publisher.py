#!/usr/bin/env python3
import struct

import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2, PointField
from std_msgs.msg import Header


class PointCloud2Publisher(Node):
    def __init__(self):
        super().__init__("pointcloud2_publisher")
        self.publisher_ = self.create_publisher(PointCloud2, "pointcloud", 10)
        timer_period = 1.0  # seconds
        self.timer = self.create_timer(timer_period, self.timer_callback)
        self.count = 0

    def timer_callback(self):
        # Create sample point cloud data
        num_points = 100
        points = np.random.rand(num_points, 3).astype(np.float32)

        # Create PointCloud2 message
        msg = PointCloud2()
        msg.header = Header()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "map"

        # Define fields
        msg.fields = [
            PointField(name="x", offset=0, datatype=PointField.FLOAT32, count=1),
            PointField(name="y", offset=4, datatype=PointField.FLOAT32, count=1),
            PointField(name="z", offset=8, datatype=PointField.FLOAT32, count=1),
        ]

        msg.is_bigendian = False
        msg.point_step = 12  # 3 * 4 bytes
        msg.row_step = msg.point_step * num_points
        msg.is_dense = True
        msg.width = num_points
        msg.height = 1

        # Pack data
        msg.data = points.tobytes()

        self.publisher_.publish(msg)
        self.get_logger().info(f"Publishing PointCloud2: {num_points} points (count: {self.count})")
        self.count += 1


def main(args=None):
    rclpy.init(args=args)
    pointcloud2_publisher = PointCloud2Publisher()
    rclpy.spin(pointcloud2_publisher)
    pointcloud2_publisher.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
