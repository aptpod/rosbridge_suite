#!/usr/bin/env python3
"""
PointCloud2 Benchmark Test for JSON mode
Measures end-to-end and rosbridge internal processing times
"""

import asyncio
import json
import statistics
import time
import websockets
from datetime import datetime, timezone


class PointCloud2BenchmarkJSON:
    def __init__(self, rosbridge_host="rosbridge", rosbridge_port=9090):
        self.rosbridge_url = f"ws://{rosbridge_host}:{rosbridge_port}"
        self.measurements = []
        self.max_measurements = 20
        self.received_count = 0
        
    async def run_benchmark(self):
        """Run the complete benchmark test"""
        print(f"Starting PointCloud2 JSON Benchmark")
        print(f"Target: {self.max_measurements} measurements")
        print(f"Connecting to: {self.rosbridge_url}")
        
        try:
            async with websockets.connect(self.rosbridge_url) as websocket:
                print("Connected to rosbridge server")
                
                # Subscribe to the benchmark topic
                subscribe_msg = {
                    "op": "subscribe",
                    "topic": "/pointcloud_benchmark",
                    "type": "sensor_msgs/PointCloud2"
                }
                
                await websocket.send(json.dumps(subscribe_msg))
                print("Subscribed to /pointcloud_benchmark")
                
                # Wait for messages and measure timing
                while self.received_count < self.max_measurements:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                        await self.process_message(message)
                    except asyncio.TimeoutError:
                        print("Timeout waiting for message")
                        break
                        
                # Generate and save benchmark report
                self.generate_report()
                
        except Exception as e:
            print(f"Benchmark failed: {e}")
            
    async def process_message(self, message):
        """Process received message and calculate timing"""
        receive_time = time.time()
        
        try:
            data = json.loads(message)
            
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
                    data_field = msg_data.get("data", "")
                    row_step = msg_data.get("row_step", 0)
                    width = msg_data.get("width", 0)
                    
                    measurement = {
                        "id": self.received_count + 1,
                        "publish_time": publish_time,
                        "receive_time": receive_time,
                        "end_to_end_ms": end_to_end_ms,
                        "message_size_bytes": len(message),
                        "data_field_size": len(data_field) if isinstance(data_field, str) else len(str(data_field)),
                        "row_step": row_step,
                        "point_count": width,
                        "encoding": "JSON",
                        "data_encoding": "base64" if isinstance(data_field, str) else "unknown"
                    }
                    
                    self.measurements.append(measurement)
                    self.received_count += 1
                    
                    print(f"JSON #{self.received_count}: "
                          f"end-to-end: {end_to_end_ms:.2f}ms, "
                          f"size: {len(message)} bytes, "
                          f"points: {width}")
                    
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON message: {e}")
        except Exception as e:
            print(f"Error processing message: {e}")
            
    def generate_report(self):
        """Generate comprehensive benchmark report"""
        if not self.measurements:
            print("No measurements collected!")
            return
            
        # Calculate statistics
        end_to_end_times = [m["end_to_end_ms"] for m in self.measurements]
        message_sizes = [m["message_size_bytes"] for m in self.measurements]
        
        report = {
            "benchmark_info": {
                "protocol": "JSON",
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
            "detailed_measurements": self.measurements,
            "summary": {
                "average_throughput_mb_per_sec": (statistics.mean(message_sizes) / (1024 * 1024)) / (statistics.mean(end_to_end_times) / 1000),
                "encoding_efficiency": "base64" if self.measurements[0]["data_encoding"] == "base64" else "unknown"
            }
        }
        
        # Save report
        timestamp = int(time.time() * 1000)
        filename = f"results/benchmark-json-{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
            
        print(f"\nJSON Benchmark Results:")
        print(f"End-to-end latency: {report['end_to_end_latency_ms']['mean']:.2f}ms (avg)")
        print(f"Range: {report['end_to_end_latency_ms']['min']:.2f} - {report['end_to_end_latency_ms']['max']:.2f}ms")
        print(f"Message size: {report['message_size_bytes']['mean']:.0f} bytes (avg)")
        print(f"Encoding: {report['summary']['encoding_efficiency']}")
        print(f"Report saved: {filename}")


async def main():
    benchmark = PointCloud2BenchmarkJSON()
    await benchmark.run_benchmark()


if __name__ == "__main__":
    asyncio.run(main())