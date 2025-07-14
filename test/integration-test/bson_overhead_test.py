#!/usr/bin/env python3
"""
BSON PointCloud2 Overhead Test
Measures BSON mode processing overhead for PointCloud2 messages
"""

import asyncio
import statistics
import time
import websockets

try:
    import bson
    BSON_AVAILABLE = True
except ImportError:
    BSON_AVAILABLE = False
    print("BSON library not available")
    exit(1)


class BSONOverheadTest:
    def __init__(self):
        self.measurements = []
        
    async def test_bson_processing(self):
        """Test BSON mode PointCloud2 processing"""
        print("Testing BSON mode PointCloud2 processing...")
        
        async with websockets.connect("ws://rosbridge-bson:9090") as ws:
            # Subscribe to benchmark topic using BSON
            subscribe_msg = bson.BSON.encode({
                "op": "subscribe",
                "topic": "/pointcloud_benchmark",
                "type": "sensor_msgs/PointCloud2"
            })
            await ws.send(subscribe_msg)
            print("Subscribed to /pointcloud_benchmark (BSON)")
            
            # Collect measurements
            measurement_count = 0
            start_time = time.time()
            
            while measurement_count < 5 and (time.time() - start_time) < 30:
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    receive_time = time.time()
                    
                    if isinstance(message, bytes):
                        data = bson.BSON(message).decode()
                        
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
                            
                            # Analyze data field
                            data_field = msg_data.get("data")
                            row_step = msg_data.get("row_step", 0)
                            width = msg_data.get("width", 0)
                            height = msg_data.get("height", 0)
                            point_step = msg_data.get("point_step", 0)
                            
                            # Determine data encoding and size
                            if isinstance(data_field, bytes):
                                data_encoding = "bson_binary"
                                data_size = len(data_field)
                            elif isinstance(data_field, str):
                                data_encoding = "base64"
                                data_size = len(data_field)
                            elif hasattr(data_field, '__len__'):
                                data_encoding = "array"
                                data_size = len(data_field)
                            else:
                                data_encoding = "unknown"
                                data_size = 0
                            
                            measurement = {
                                "id": measurement_count + 1,
                                "total_message_size": len(message),
                                "data_field_size": data_size,
                                "data_encoding": data_encoding,
                                "data_field_type": type(data_field).__name__,
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
                            print(f"  Data field size: {data_size:,} bytes")
                            print(f"  Data encoding: {data_encoding} ({type(data_field).__name__})")
                            print(f"  Points: {width:,}")
                            print(f"  Row step: {row_step:,} bytes")
                            if end_to_end_ms:
                                print(f"  End-to-end time: {end_to_end_ms:.2f}ms")
                            print()
                            
                except asyncio.TimeoutError:
                    print("Timeout waiting for message")
                    break
                except Exception as e:
                    print(f"Error processing message: {e}")
                    import traceback
                    traceback.print_exc()
                    
    def analyze_overhead(self):
        """Analyze BSON PointCloud2 processing overhead"""
        if not self.measurements:
            print("No measurements collected!")
            return
            
        print("="*60)
        print("POINTCLOUD2 BSON MODE OVERHEAD ANALYSIS")
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
        print(f"  Average data field size: {statistics.mean(data_sizes):,.0f} bytes")
        print(f"  Expected raw data size: {statistics.mean(row_steps):,.0f} bytes")
        print(f"  Data encoding: {self.measurements[0]['data_encoding']}")
        print(f"  Data field type: {self.measurements[0]['data_field_type']}")
        
        # Encoding efficiency analysis
        avg_data_size = statistics.mean(data_sizes)
        avg_row_step = statistics.mean(row_steps)
        
        if self.measurements[0]['data_encoding'] == 'bson_binary':
            # BSON Binary mode - should be close to raw data size
            efficiency_ratio = avg_data_size / avg_row_step
            overhead_percent = (efficiency_ratio - 1) * 100
            
            print(f"\nBSON Binary Encoding Efficiency:")
            print(f"  Raw data size: {avg_row_step:,.0f} bytes")
            print(f"  BSON Binary size: {avg_data_size:,.0f} bytes")
            print(f"  Efficiency ratio: {efficiency_ratio:.3f}")
            print(f"  Overhead: {overhead_percent:.1f}%")
            
            if overhead_percent < 5:
                print(f"  ✅ Excellent efficiency! BSON Binary adds only {overhead_percent:.1f}% overhead")
            elif overhead_percent < 15:
                print(f"  🟡 Good efficiency. BSON Binary adds {overhead_percent:.1f}% overhead")
            else:
                print(f"  🔴 High overhead detected! BSON Binary adds {overhead_percent:.1f}% overhead")
                
        elif self.measurements[0]['data_encoding'] == 'base64':
            # Fallback to Base64 - not optimal
            base64_overhead = (avg_data_size / avg_row_step - 1) * 100
            print(f"\nBase64 Encoding (Fallback):")
            print(f"  Raw data size: {avg_row_step:,.0f} bytes")
            print(f"  Base64 encoded size: {avg_data_size:,.0f} characters")
            print(f"  Overhead: {base64_overhead:.1f}%")
            print(f"  ⚠️ BSON mode falling back to Base64 encoding!")
            
        # Network overhead
        avg_total = statistics.mean(total_sizes)
        protocol_overhead = avg_total - avg_data_size
        protocol_overhead_percent = (protocol_overhead / avg_total) * 100
        
        print(f"\nProtocol Overhead:")
        print(f"  Total message size: {avg_total:,.0f} bytes")
        print(f"  Data field size: {avg_data_size:,.0f} bytes")
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
        
        # Encoding status summary
        bson_binary_count = len([m for m in self.measurements if m["data_encoding"] == "bson_binary"])
        base64_count = len([m for m in self.measurements if m["data_encoding"] == "base64"])
        
        print(f"\nEncoding Summary:")
        print(f"  BSON Binary messages: {bson_binary_count}")
        print(f"  Base64 fallback messages: {base64_count}")
        
        if bson_binary_count > base64_count:
            print(f"  ✅ BSON Binary encoding is working efficiently")
        else:
            print(f"  ❌ BSON mode is falling back to Base64 encoding")
        
        print("\n" + "="*60)
        
    async def run_test(self):
        """Run the complete test"""
        print("PointCloud2 BSON Mode Overhead Test")
        print("Waiting for benchmark publisher...")
        await asyncio.sleep(3)
        
        try:
            await self.test_bson_processing()
            self.analyze_overhead()
            
        except Exception as e:
            print(f"Test failed: {e}")
            import traceback
            traceback.print_exc()


async def main():
    test = BSONOverheadTest()
    await test.run_test()


if __name__ == "__main__":
    asyncio.run(main())