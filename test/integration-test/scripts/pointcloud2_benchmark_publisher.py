#!/usr/bin/env python3
import numpy as np
import rclpy
import time
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2, PointField
from std_msgs.msg import Header


class PointCloud2BenchmarkPublisher(Node):
    def __init__(self):
        super().__init__("pointcloud2_benchmark_publisher")
        self.publisher_ = self.create_publisher(PointCloud2, "pointcloud_benchmark", 10)
        
        # Calculate for row_step = 600000 (approximately 600KB to fit WebSocket limits)
        # Point step: 3 floats * 4 bytes = 12 bytes per point
        # Number of points = row_step / point_step = 600000 / 12 = 50000 points
        self.target_row_step = 600000
        self.point_step = 12  # 3 * 4 bytes (x, y, z as float32)
        self.num_points = self.target_row_step // self.point_step
        
        self.get_logger().info(f"Configured for {self.num_points} points, row_step: {self.target_row_step}")
        
        # Track publishing timing
        self.publish_count = 0
        self.max_publishes = 50  # Increased for continuous testing
        
        # Start benchmark immediately
        self.create_timer(1.0, self.start_benchmark)
        
    def start_benchmark(self):
        """Start the benchmark publishing sequence"""
        self.get_logger().info("Starting PointCloud2 benchmark sequence...")
        self.benchmark_timer = self.create_timer(2.0, self.benchmark_callback)  # Faster publishing
        
    def benchmark_callback(self):
        """Publish one benchmark message"""
        if self.publish_count >= self.max_publishes:
            self.get_logger().info("Benchmark publishing completed!")
            self.benchmark_timer.cancel()
            return
            
        start_time = time.time()
        
        # Generate large point cloud data
        points = np.random.rand(self.num_points, 3).astype(np.float32)
        
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
        msg.point_step = self.point_step
        msg.row_step = self.target_row_step
        msg.is_dense = True
        msg.width = self.num_points
        msg.height = 1
        
        # Pack data
        msg.data = points.tobytes()
        
        # Add timestamp for end-to-end measurement
        msg.header.stamp = self.get_clock().now().to_msg()
        
        # Publish message
        self.publisher_.publish(msg)
        
        publish_time = time.time() - start_time
        
        self.get_logger().info(
            f"Published benchmark PointCloud2 #{self.publish_count + 1}: "
            f"{self.num_points} points, {len(msg.data)} bytes, "
            f"publish_time: {publish_time*1000:.2f}ms"
        )
        
        self.publish_count += 1


def main(args=None):
    rclpy.init(args=args)
    publisher = PointCloud2BenchmarkPublisher()
    rclpy.spin(publisher)
    publisher.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()