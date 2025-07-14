#!/usr/bin/env python3
"""
PointCloud2 Benchmark Test for BSON mode
Measures end-to-end and rosbridge internal processing times
"""

import asyncio
import json
import statistics
import time
import websockets
from datetime import datetime, timezone

try:
    import bson
except ImportError:
    print("BSON library not available. Install with: pip install pymongo")
    exit(1)


class PointCloud2BenchmarkBSON:
    def __init__(self, rosbridge_host="rosbridge-bson", rosbridge_port=9090):
        self.rosbridge_url = f"ws://{rosbridge_host}:{rosbridge_port}"
        self.measurements = []
        self.max_measurements = 10  # Reduced for testing
        self.received_count = 0
        
    async def run_benchmark(self):
        """Run the complete benchmark test"""
        print(f"Starting PointCloud2 BSON Benchmark")
        print(f"Target: {self.max_measurements} measurements")
        print(f"Connecting to: {self.rosbridge_url}")
        
        try:
            async with websockets.connect(self.rosbridge_url) as websocket:
                print("Connected to rosbridge server")
                
                # Subscribe to the benchmark topic using BSON
                subscribe_msg = bson.BSON.encode({
                    "op": "subscribe",
                    "topic": "/pointcloud_benchmark",
                    "type": "sensor_msgs/PointCloud2"
                })
                
                await websocket.send(subscribe_msg)
                print("Subscribed to /pointcloud_benchmark (BSON)")
                
                # Wait for messages and measure timing
                while self.received_count < self.max_measurements:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                        await self.process_message(message)
                    except asyncio.TimeoutError:
                        print("Timeout waiting for message")
                        break
                        
                # Generate and save benchmark report
                self.generate_report()
                
        except Exception as e:
            print(f"Benchmark failed: {e}")
            
    async def process_message(self, message):
        """Process received BSON message and calculate timing"""
        receive_time = time.time()
        
        try:
            # Decode BSON message
            if isinstance(message, bytes):
                # Promote binary fields to native types for easier access
                data = bson.BSON(message).decode(promote_buffers=True)
            else:
                print(f"Unexpected message type: {type(message)}")
                return
                
            if data.get("topic") == "/pointcloud_benchmark":
                msg_data = data.get("msg", {})
                header = msg_data.get("header", {})
                stamp = header.get("stamp", {})
                
                # Extract publish timestamp (ROS time in seconds + nanoseconds)
                if stamp:
                    publish_time_sec = stamp.get("sec", 0)
                    publish_time_nanosec = stamp.get("nanosec", 0)
                    publish_time = publish_time_sec + (publish_time_nanosec / 1e9)
                    
                    # Calculate end-to-end latency
                    end_to_end_ms = (receive_time - publish_time) * 1000
                    
                    # Get message size info
                    data_field = msg_data.get("data")
                    row_step = msg_data.get("row_step", 0)
                    width = msg_data.get("width", 0)
                    
                    # Analyze data field encoding
                    data_encoding = "unknown"
                    data_size = 0
                    
                    if isinstance(data_field, bytes):
                        data_encoding = "bson_binary"
                        data_size = len(data_field)
                    elif isinstance(data_field, str):
                        data_encoding = "base64"
                        data_size = len(data_field)
                    elif hasattr(data_field, '__len__'):
                        data_encoding = "array"
                        data_size = len(data_field)
                    
                    measurement = {
                        "id": self.received_count + 1,
                        "publish_time": publish_time,
                        "receive_time": receive_time,
                        "end_to_end_ms": end_to_end_ms,
                        "message_size_bytes": len(message),
                        "data_field_size": data_size,
                        "row_step": row_step,
                        "point_count": width,
                        "encoding": "BSON",
                        "data_encoding": data_encoding,
                        "data_field_type": str(type(data_field).__name__)
                    }
                    
                    self.measurements.append(measurement)
                    self.received_count += 1
                    
                    print(f"BSON #{self.received_count}: "
                          f"end-to-end: {end_to_end_ms:.2f}ms, "
                          f"size: {len(message)} bytes, "
                          f"points: {width}, "
                          f"data: {data_encoding}")
                    
        except Exception as e:
            print(f"Error processing BSON message: {e}")
            import traceback
            traceback.print_exc()
            
    def generate_report(self):
        """Generate comprehensive benchmark report"""
        if not self.measurements:
            print("No measurements collected!")
            return
            
        # Calculate statistics
        end_to_end_times = [m["end_to_end_ms"] for m in self.measurements]
        message_sizes = [m["message_size_bytes"] for m in self.measurements]
        
        # Check encoding efficiency
        bson_binary_count = len([m for m in self.measurements if m["data_encoding"] == "bson_binary"])
        base64_count = len([m for m in self.measurements if m["data_encoding"] == "base64"])
        
        report = {
            "benchmark_info": {
                "protocol": "BSON",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_measurements": len(self.measurements),
                "target_measurements": self.max_measurements
            },
            "end_to_end_latency_ms": {
                "min": min(end_to_end_times),
                "max": max(end_to_end_times),
                "mean": statistics.mean(end_to_end_times),
                "median": statistics.median(end_to_end_times),
                "stdev": statistics.stdev(end_to_end_times) if len(end_to_end_times) > 1 else 0
            },
            "message_size_bytes": {
                "min": min(message_sizes),
                "max": max(message_sizes),
                "mean": statistics.mean(message_sizes),
                "median": statistics.median(message_sizes)
            },
            "encoding_analysis": {
                "bson_binary_messages": bson_binary_count,
                "base64_messages": base64_count,
                "efficiency_status": "EFFICIENT" if bson_binary_count > base64_count else "INEFFICIENT"
            },
            "detailed_measurements": self.measurements,
            "summary": {
                "average_throughput_mb_per_sec": (statistics.mean(message_sizes) / (1024 * 1024)) / (statistics.mean(end_to_end_times) / 1000),
                "primary_encoding": "bson_binary" if bson_binary_count > base64_count else "base64"
            }
        }
        
        # Save report
        timestamp = int(time.time() * 1000)
        filename = f"results/benchmark-bson-{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
            
        print(f"\nBSON Benchmark Results:")
        print(f"End-to-end latency: {report['end_to_end_latency_ms']['mean']:.2f}ms (avg)")
        print(f"Range: {report['end_to_end_latency_ms']['min']:.2f} - {report['end_to_end_latency_ms']['max']:.2f}ms")
        print(f"Message size: {report['message_size_bytes']['mean']:.0f} bytes (avg)")
        print(f"Primary encoding: {report['summary']['primary_encoding']}")
        print(f"Efficiency: {report['encoding_analysis']['efficiency_status']}")
        print(f"Report saved: {filename}")


async def main():
    benchmark = PointCloud2BenchmarkBSON()
    await benchmark.run_benchmark()


if __name__ == "__main__":
    asyncio.run(main())