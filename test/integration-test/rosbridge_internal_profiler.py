#!/usr/bin/env python3
"""
Rosbridge Internal Processing Profiler
Measures DDS(C++) -> Python -> BSON conversion overhead inside rosbridge server
"""

import time
import sys
import os

# Add rosbridge libraries to Python path for direct measurement
sys.path.insert(0, '/opt/ros/humble/lib/python3.10/site-packages')

try:
    from rosbridge_library.internal.message_conversion import extract_json_values, extract_bson_values
    from rosbridge_library.internal.outgoing_message import OutgoingMessage
    from sensor_msgs.msg import PointCloud2, PointField
    from std_msgs.msg import Header
    import numpy as np
    import rclpy
    from rclpy.node import Node
    import statistics
except ImportError as e:
    print(f"Required libraries not available: {e}")
    sys.exit(1)


class RosbridgeInternalProfiler(Node):
    def __init__(self):
        super().__init__('rosbridge_internal_profiler')
        self.measurements = []
        
    def create_pointcloud2_message(self, num_points=50000):
        """Create a PointCloud2 message similar to benchmark publisher"""
        # Generate test data
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
        
        return msg
        
    def profile_conversion_overhead(self, msg, iterations=10):
        """Profile the conversion overhead: ROS2 Message -> Python Dict -> BSON"""
        
        print(f"Profiling conversion overhead with {iterations} iterations...")
        print(f"Message info: {len(msg.data)} bytes, {msg.width} points")
        
        json_times = []
        bson_times = []
        
        for i in range(iterations):
            print(f"Iteration {i+1}/{iterations}")
            
            # Create OutgoingMessage wrapper (simulates rosbridge processing)
            outgoing_msg = OutgoingMessage(msg)
            
            # Measure JSON conversion time
            start_time = time.time()
            json_values = outgoing_msg.get_json_values()
            json_time = time.time() - start_time
            json_times.append(json_time * 1000)  # Convert to milliseconds
            
            # Measure BSON conversion time  
            start_time = time.time()
            bson_values = outgoing_msg.get_bson_values()
            bson_time = time.time() - start_time
            bson_times.append(bson_time * 1000)  # Convert to milliseconds
            
            # Analyze data sizes
            if i == 0:  # First iteration - analyze data structure
                json_data_field = json_values.get("data", "")
                bson_data_field = bson_values.get("data", b"")
                
                measurement = {
                    "original_data_size": len(msg.data),
                    "json_data_size": len(json_data_field) if isinstance(json_data_field, str) else 0,
                    "bson_data_size": len(bson_data_field) if isinstance(bson_data_field, bytes) else 0,
                    "json_data_type": type(json_data_field).__name__,
                    "bson_data_type": type(bson_data_field).__name__,
                    "json_conversion_time": json_time * 1000,
                    "bson_conversion_time": bson_time * 1000
                }
                
                self.measurements.append(measurement)
                
                print(f"  Original data: {len(msg.data)} bytes")
                print(f"  JSON data: {len(json_data_field)} chars ({type(json_data_field).__name__})")
                print(f"  BSON data: {len(bson_data_field)} bytes ({type(bson_data_field).__name__})")
                print(f"  JSON conversion: {json_time*1000:.3f}ms")
                print(f"  BSON conversion: {bson_time*1000:.3f}ms")
                print()
                
        return json_times, bson_times
        
    def analyze_results(self, json_times, bson_times):
        """Analyze and report the conversion overhead results"""
        
        print("="*70)
        print("ROSBRIDGE INTERNAL PROCESSING OVERHEAD ANALYSIS")
        print("="*70)
        
        # Basic statistics
        json_avg = statistics.mean(json_times)
        json_min = min(json_times)
        json_max = max(json_times)
        json_std = statistics.stdev(json_times) if len(json_times) > 1 else 0
        
        bson_avg = statistics.mean(bson_times)
        bson_min = min(bson_times)
        bson_max = max(bson_times)
        bson_std = statistics.stdev(bson_times) if len(bson_times) > 1 else 0
        
        print(f"\nConversion Time Analysis:")
        print(f"  JSON Conversion:")
        print(f"    Average: {json_avg:.3f}ms")
        print(f"    Range: {json_min:.3f} - {json_max:.3f}ms")
        print(f"    Std Dev: {json_std:.3f}ms")
        
        print(f"  BSON Conversion:")
        print(f"    Average: {bson_avg:.3f}ms")
        print(f"    Range: {bson_min:.3f} - {bson_max:.3f}ms")
        print(f"    Std Dev: {bson_std:.3f}ms")
        
        # Performance comparison
        if bson_avg > 0:
            speed_ratio = json_avg / bson_avg
            time_diff = json_avg - bson_avg
            
            print(f"\nPerformance Comparison:")
            print(f"  Time difference: {time_diff:.3f}ms")
            print(f"  Speed ratio: {speed_ratio:.2f}x")
            
            if time_diff > 0:
                print(f"  ✅ BSON conversion is {time_diff:.3f}ms faster ({speed_ratio:.2f}x)")
            else:
                print(f"  ⚠️ JSON conversion is {abs(time_diff):.3f}ms faster")
                
        # Data efficiency analysis
        if self.measurements:
            m = self.measurements[0]
            
            print(f"\nData Efficiency Analysis:")
            print(f"  Original data size: {m['original_data_size']:,} bytes")
            print(f"  JSON encoded size: {m['json_data_size']:,} chars")
            print(f"  BSON encoded size: {m['bson_data_size']:,} bytes")
            
            # Calculate overhead
            json_overhead = (m['json_data_size'] / m['original_data_size'] - 1) * 100
            bson_overhead = (m['bson_data_size'] / m['original_data_size'] - 1) * 100
            
            print(f"  JSON overhead: {json_overhead:.1f}%")
            print(f"  BSON overhead: {bson_overhead:.1f}%")
            
            efficiency_gain = json_overhead - bson_overhead
            print(f"  BSON efficiency gain: {efficiency_gain:.1f}%")
            
            # Encoding analysis
            print(f"\nEncoding Analysis:")
            print(f"  JSON data type: {m['json_data_type']}")
            print(f"  BSON data type: {m['bson_data_type']}")
            
            if m['bson_data_type'] == 'bytes':
                print(f"  ✅ BSON using efficient binary encoding")
            else:
                print(f"  ⚠️ BSON not using binary encoding")
                
        print("\n" + "="*70)
        
    def run_profile(self):
        """Run the complete profiling session"""
        print("Rosbridge Internal Processing Profiler")
        print("Measuring DDS(C++) -> Python -> BSON conversion overhead")
        
        try:
            # Create test message
            msg = self.create_pointcloud2_message(50000)  # 600KB data
            
            # Profile conversion overhead
            json_times, bson_times = self.profile_conversion_overhead(msg, iterations=20)
            
            # Analyze results
            self.analyze_results(json_times, bson_times)
            
        except Exception as e:
            print(f"Profiling failed: {e}")
            import traceback
            traceback.print_exc()


def main(args=None):
    rclpy.init(args=args)
    
    profiler = RosbridgeInternalProfiler()
    
    try:
        profiler.run_profile()
    finally:
        profiler.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()