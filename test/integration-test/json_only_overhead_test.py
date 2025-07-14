#!/usr/bin/env python3
"""
JSON Only PointCloud2 Overhead Test
Quick test to measure rosbridge server processing for PointCloud2 messages
"""

import asyncio
import json
import time
import websockets
import statistics


class JSONOverheadTest:
    def __init__(self):
        self.measurements = []
        
    async def test_json_processing(self):
        """Test JSON mode PointCloud2 processing"""
        print("Testing JSON mode PointCloud2 processing...")
        
        async with websockets.connect("ws://rosbridge:9090") as ws:
            # Subscribe to benchmark topic
            subscribe_msg = {
                "op": "subscribe",
                "topic": "/pointcloud_benchmark",
                "type": "sensor_msgs/PointCloud2"
            }
            await ws.send(json.dumps(subscribe_msg))
            print("Subscribed to /pointcloud_benchmark")
            
            # Collect measurements
            measurement_count = 0
            start_time = time.time()
            
            while measurement_count < 5 and (time.time() - start_time) < 30:
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    receive_time = time.time()
                    
                    data = json.loads(message)
                    if data.get("topic") == "/pointcloud_benchmark":
                        msg_data = data.get("msg", {})
                        header = msg_data.get("header", {})
                        stamp = header.get("stamp", {})
                        
                        # Calculate end-to-end time if possible
                        end_to_end_ms = None
                        if stamp:
                            publish_time_sec = stamp.get("sec", 0)
                            publish_time_nanosec = stamp.get("nanosec", 0)
                            publish_time = publish_time_sec + (publish_time_nanosec / 1e9)
                            end_to_end_ms = (receive_time - publish_time) * 1000
                        
                        # Analyze message structure
                        data_field = msg_data.get("data", "")
                        row_step = msg_data.get("row_step", 0)
                        width = msg_data.get("width", 0)
                        height = msg_data.get("height", 0)
                        point_step = msg_data.get("point_step", 0)
                        
                        measurement = {
                            "id": measurement_count + 1,
                            "total_message_size": len(message),
                            "data_field_size": len(data_field) if isinstance(data_field, str) else 0,
                            "data_encoding": "base64" if isinstance(data_field, str) else type(data_field).__name__,
                            "points": width,
                            "row_step": row_step,
                            "point_step": point_step,
                            "expected_data_size": row_step,
                            "receive_time": receive_time,
                            "end_to_end_ms": end_to_end_ms
                        }
                        
                        self.measurements.append(measurement)
                        measurement_count += 1
                        
                        print(f"Measurement #{measurement_count}:")
                        print(f"  Total message size: {len(message):,} bytes")
                        print(f"  Data field size: {len(data_field):,} chars")
                        print(f"  Points: {width:,}")
                        print(f"  Row step: {row_step:,} bytes")
                        print(f"  Data encoding: {measurement['data_encoding']}")
                        if end_to_end_ms:
                            print(f"  End-to-end time: {end_to_end_ms:.2f}ms")
                        print()
                        
                except asyncio.TimeoutError:
                    print("Timeout waiting for message")
                    break
                except json.JSONDecodeError as e:
                    print(f"JSON decode error: {e}")
                except Exception as e:
                    print(f"Error processing message: {e}")
                    
    def analyze_overhead(self):
        """Analyze PointCloud2 processing overhead"""
        if not self.measurements:
            print("No measurements collected!")
            return
            
        print("="*60)
        print("POINTCLOUD2 JSON MODE OVERHEAD ANALYSIS")
        print("="*60)
        
        # Basic statistics
        total_sizes = [m["total_message_size"] for m in self.measurements]
        data_sizes = [m["data_field_size"] for m in self.measurements]
        row_steps = [m["row_step"] for m in self.measurements]
        end_to_end_times = [m["end_to_end_ms"] for m in self.measurements if m["end_to_end_ms"]]
        
        print(f"\nMessage Size Analysis:")
        print(f"  Total messages analyzed: {len(self.measurements)}")
        print(f"  Average total message size: {statistics.mean(total_sizes):,.0f} bytes")
        print(f"  Message size range: {min(total_sizes):,} - {max(total_sizes):,} bytes")
        
        print(f"\nData Field Analysis:")
        print(f"  Average data field size: {statistics.mean(data_sizes):,.0f} chars")
        print(f"  Expected raw data size: {statistics.mean(row_steps):,.0f} bytes")
        print(f"  Data encoding: {self.measurements[0]['data_encoding']}")
        
        # Base64 overhead calculation
        if self.measurements[0]['data_encoding'] == 'base64':
            avg_data_chars = statistics.mean(data_sizes)
            avg_row_step = statistics.mean(row_steps)
            
            # Base64 encodes 3 bytes as 4 characters
            expected_base64_chars = (avg_row_step * 4) / 3
            base64_overhead = (avg_data_chars / avg_row_step - 1) * 100
            
            print(f"\nBase64 Encoding Overhead:")
            print(f"  Raw data size: {avg_row_step:,.0f} bytes")
            print(f"  Base64 encoded size: {avg_data_chars:,.0f} characters")
            print(f"  Expected Base64 size: {expected_base64_chars:,.0f} characters")
            print(f"  Overhead: {base64_overhead:.1f}%")
            
            if base64_overhead > 30:
                print(f"  🔴 High overhead detected! Base64 adds {base64_overhead:.1f}% to data size")
            else:
                print(f"  🟡 Normal Base64 overhead: {base64_overhead:.1f}%")
        
        # Network overhead
        avg_total = statistics.mean(total_sizes)
        avg_data = statistics.mean(data_sizes)
        protocol_overhead = avg_total - avg_data
        protocol_overhead_percent = (protocol_overhead / avg_total) * 100
        
        print(f"\nProtocol Overhead:")
        print(f"  Total message size: {avg_total:,.0f} bytes")
        print(f"  Data field size: {avg_data:,.0f} bytes")
        print(f"  Protocol overhead: {protocol_overhead:,.0f} bytes ({protocol_overhead_percent:.1f}%)")
        
        # Performance analysis
        if end_to_end_times:
            print(f"\nPerformance Analysis:")
            print(f"  Average end-to-end latency: {statistics.mean(end_to_end_times):.2f}ms")
            print(f"  Latency range: {min(end_to_end_times):.2f} - {max(end_to_end_times):.2f}ms")
            print(f"  Latency std dev: {statistics.stdev(end_to_end_times):.2f}ms")
            
            # Throughput calculation
            avg_throughput_mbps = (avg_total * 8) / (statistics.mean(end_to_end_times) / 1000) / 1_000_000
            print(f"  Estimated throughput: {avg_throughput_mbps:.2f} Mbps")
        
        print("\n" + "="*60)
        
    async def run_test(self):
        """Run the complete test"""
        print("PointCloud2 JSON Mode Overhead Test")
        print("Waiting for benchmark publisher...")
        await asyncio.sleep(3)
        
        try:
            await self.test_json_processing()
            self.analyze_overhead()
            
        except Exception as e:
            print(f"Test failed: {e}")
            import traceback
            traceback.print_exc()


async def main():
    test = JSONOverheadTest()
    await test.run_test()


if __name__ == "__main__":
    asyncio.run(main())