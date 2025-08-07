#!/usr/bin/env python3

import os
import sys
import threading
import time
from datetime import datetime

import websocket
from bson import decode, encode

ROSBRIDGE_URL = os.environ.get("ROSBRIDGE_URL_BSON", "ws://localhost:9091")
RESULTS_DIR = os.environ.get("RESULTS_DIR", "/results")

print("Starting BSON mode server BSON test...")
print(f"Connecting to: {ROSBRIDGE_URL}")


class ROSBridgeBSONModeBSONTest:
    def __init__(self):
        self.results = {
            "mode": "BSON_Mode_BSON",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "tests": [],
        }
        self.message_count = {"chatter": 0, "pointcloud": 0}
        self.validation_results = {
            "chatter": {"required": 2, "validated": 0, "success": False},
            "pointcloud": {"required": 2, "validated": 0, "success": False},
        }
        self.ws = None
        self.test_completed = False

    def validate_chatter_message(self, data):
        """Validate chatter message contains 'Hello World' pattern"""
        return data and isinstance(data, str) and "Hello World" in data

    def is_base64_encoded(self, data):
        """Check if data appears to be base64 encoded"""
        import base64
        import re

        if isinstance(data, str):
            # Check if it looks like base64 (alphanumeric + / + = padding)
            if re.match(r"^[A-Za-z0-9+/]*={0,2}$", data) and len(data) % 4 == 0:
                try:
                    base64.b64decode(data)
                    return True
                except Exception:
                    return False
        return False

    def analyze_pointcloud_data(self, msg):
        """Analyze PointCloud2 data field format and content"""
        data_field = msg.get("data")
        if not data_field:
            return {"analysis": "no_data", "size": 0, "format": "unknown"}

        analysis = {
            "size": len(data_field) if isinstance(data_field, (str, list)) else 0,
            "type": type(data_field).__name__,
            "format": "unknown",
        }

        if isinstance(data_field, str):
            analysis["format"] = "base64" if self.is_base64_encoded(data_field) else "string"
            # Log first 50 chars for inspection
            analysis["preview"] = data_field[:50] + ("..." if len(data_field) > 50 else "")
        elif isinstance(data_field, list):
            analysis["format"] = "array"
            analysis["length"] = len(data_field)
            # Log first few elements
            analysis["preview"] = str(data_field[:10]) + ("..." if len(data_field) > 10 else "")
        elif hasattr(data_field, "__class__") and "Binary" in str(type(data_field)):
            analysis["format"] = "bson_binary"
            analysis["size"] = len(data_field) if hasattr(data_field, "__len__") else 0
            analysis["preview"] = f"BSON Binary object: {str(type(data_field))}"
            analysis["is_true_binary"] = True
        else:
            # Check for other types that might indicate binary data
            analysis["preview"] = f"Unknown type: {str(type(data_field))}"

        return analysis

    def validate_pointcloud_message(self, msg):
        """Validate PointCloud2 has valid structure and analyze data format"""
        data_analysis = self.analyze_pointcloud_data(msg)

        # Log detailed analysis
        print("  📊 PointCloud2 data analysis:")
        print(f"     Type: {data_analysis['type']}")
        print(f"     Format: {data_analysis['format']}")
        print(f"     Size: {data_analysis['size']}")
        if "preview" in data_analysis:
            print(f"     Preview: {data_analysis['preview']}")
        if "length" in data_analysis:
            print(f"     Array length: {data_analysis['length']}")

        # Store analysis in test results for later inspection
        if not hasattr(self, "pointcloud_analyses"):
            self.pointcloud_analyses = []
        self.pointcloud_analyses.append(data_analysis)

        return (
            msg.get("width", 0) > 0
            and msg.get("height", 0) >= 1
            and msg.get("data")
            and len(msg.get("data", [])) > 0
        )

    def check_test_completion(self):
        """Check if validation requirements are met"""
        if (
            self.validation_results["chatter"]["validated"]
            >= self.validation_results["chatter"]["required"]
            and self.validation_results["pointcloud"]["validated"]
            >= self.validation_results["pointcloud"]["required"]
        ):

            all_tests_passed = (
                self.validation_results["chatter"]["success"]
                and self.validation_results["pointcloud"]["success"]
            )

            if all_tests_passed:
                print("✅ All BSON validation tests passed! Closing connection...")
                self.results["overall_status"] = "PASSED"
            else:
                print("❌ BSON validation tests failed!")
                self.results["overall_status"] = "FAILED"

            self.test_completed = True
            if self.ws:
                self.ws.close()

    def on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            # In hybrid mode, we might receive both BSON and JSON responses
            if isinstance(message, bytes):
                try:
                    msg = decode(message)
                    print(f"Received BSON message: {len(message)} bytes")
                except Exception as e:
                    print(f"Failed to decode BSON message: {e}")
                    return
            else:
                # Fallback to JSON if not binary
                import json

                msg = json.loads(message)
                print(f"Received JSON message: {len(message)} chars")

            if msg.get("topic") == "/chatter":
                self.message_count["chatter"] += 1
                is_valid = self.validate_chatter_message(msg["msg"]["data"])
                data_size = len(message) if isinstance(message, bytes) else len(str(message))

                print(
                    f"Received chatter message #{self.message_count['chatter']}: {msg['msg']['data']} [{'✓' if is_valid else '✗'}] ({data_size} bytes)"
                )

                if self.message_count["chatter"] <= self.validation_results["chatter"]["required"]:
                    self.validation_results["chatter"]["validated"] += 1
                    if is_valid:
                        self.validation_results["chatter"]["success"] = True

                self.results["tests"].append(
                    {
                        "test": "chatter_subscribe_bson",
                        "status": "success" if is_valid else "validation_failed",
                        "message": f"Received message: {msg['msg']['data']}",
                        "validation": is_valid,
                        "data_size": data_size,
                    }
                )

                self.check_test_completion()

            elif msg.get("topic") == "/pointcloud":
                self.message_count["pointcloud"] += 1
                num_points = msg["msg"]["width"]
                is_valid = self.validate_pointcloud_message(msg["msg"])
                data_size = len(message) if isinstance(message, bytes) else len(str(message))

                print(
                    f"Received pointcloud message #{self.message_count['pointcloud']}: {num_points} points [{'✓' if is_valid else '✗'}] ({data_size} bytes)"
                )

                if (
                    self.message_count["pointcloud"]
                    <= self.validation_results["pointcloud"]["required"]
                ):
                    self.validation_results["pointcloud"]["validated"] += 1
                    if is_valid:
                        self.validation_results["pointcloud"]["success"] = True

                self.results["tests"].append(
                    {
                        "test": "pointcloud_subscribe_bson",
                        "status": "success" if is_valid else "validation_failed",
                        "message": f"Received pointcloud with {num_points} points",
                        "validation": is_valid,
                        "data_size": data_size,
                    }
                )

                self.check_test_completion()

            elif msg.get("op") == "service_response":
                data_size = len(message) if isinstance(message, bytes) else len(str(message))
                print("Received service response:", msg)
                self.results["tests"].append(
                    {
                        "test": "service_call_bson",
                        "status": "success",
                        "service": msg.get("service"),
                        "result": msg.get("result", msg.get("values")),
                        "data_size": data_size,
                    }
                )

        except Exception as e:
            print(f"Error parsing BSON message: {e}")
            self.results["tests"].append({"test": "bson_parse", "status": "error", "error": str(e)})
            self.results["overall_status"] = "FAILED"
            if self.ws:
                self.ws.close()

    def on_error(self, ws, error):
        """Handle WebSocket errors"""
        print(f"WebSocket error: {error}")
        print(f"Error type: {type(error)}")
        print(f"WebSocket URL: {ROSBRIDGE_URL}")
        self.results["tests"].append(
            {
                "test": "connection_bson",
                "status": "error",
                "error": str(error),
                "error_type": str(type(error)),
            }
        )

    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        print("Connection closed")
        print(
            f"Total messages received - Chatter: {self.message_count['chatter']}, PointCloud: {self.message_count['pointcloud']}"
        )
        chatter_status = "PASS" if self.validation_results["chatter"]["success"] else "FAIL"
        pointcloud_status = "PASS" if self.validation_results["pointcloud"]["success"] else "FAIL"
        print(f"Validation results - Chatter: {chatter_status}, PointCloud: {pointcloud_status}")

        self.results["summary"] = {
            "total_messages": self.message_count,
            "validation_results": self.validation_results,
            "connection": "closed",
        }

        self.save_results()

        # Exit with appropriate code
        if self.results.get("overall_status") == "PASSED":
            print("🎉 BSON mode test PASSED")
            sys.exit(0)
        else:
            print("💥 BSON mode test FAILED")
            sys.exit(1)

    def on_open(self, ws):
        """Handle WebSocket connection open"""
        print("Connected to BSON mode server (BSON mode)")
        print(f"Connected to: {ROSBRIDGE_URL}")
        print("Starting BSON message sending...")

        def send_subscriptions():
            # Test 1: Subscribe to chatter topic
            print("Test 1: Subscribing to /chatter topic...")
            subscribe_chatter = {
                "op": "subscribe",
                "topic": "/chatter",
                "type": "std_msgs/msg/String",
            }
            try:
                bson_data = encode(subscribe_chatter)
                print(f"Sending BSON data: {len(bson_data)} bytes")
                ws.send(bson_data, websocket.ABNF.OPCODE_BINARY)
                print("BSON subscribe message sent successfully")
            except Exception as e:
                print(f"Error sending BSON message: {e}")

            # Test 2: Subscribe to pointcloud topic
            time.sleep(1)
            print("Test 2: Subscribing to /pointcloud topic...")
            subscribe_pointcloud = {
                "op": "subscribe",
                "topic": "/pointcloud",
                "type": "sensor_msgs/msg/PointCloud2",
            }
            ws.send(encode(subscribe_pointcloud), websocket.ABNF.OPCODE_BINARY)

            # Test 3: Call echo service
            time.sleep(2)
            print("Test 3: Calling /echo_set_bool service...")
            call_service = {
                "op": "call_service",
                "service": "/echo_set_bool",
                "type": "std_srvs/srv/SetBool",
                "args": {"data": True},
            }
            ws.send(encode(call_service), websocket.ABNF.OPCODE_BINARY)

            # Test 4: Call add two ints service
            time.sleep(3)
            print("Test 4: Calling /echo_add_two_ints service...")
            call_service2 = {
                "op": "call_service",
                "service": "/echo_add_two_ints",
                "type": "example_interfaces/srv/AddTwoInts",
                "args": {"a": 5, "b": 3},
            }
            ws.send(encode(call_service2), websocket.ABNF.OPCODE_BINARY)

            # Test 5: Publish binary data to test BSON Binary handling
            time.sleep(2)
            print("Test 5: Publishing binary data with uint8[] field...")

            # Create a test message with binary data
            # import base64  # Removed unused import

            test_binary_data = bytes(range(100))  # Create 100 bytes of test data

            # Test publishing raw binary in BSON
            publish_msg = {
                "op": "publish",
                "topic": "/test_binary",
                "type": "std_msgs/msg/UInt8MultiArray",
                "msg": {
                    "layout": {"dim": [], "data_offset": 0},
                    "data": list(test_binary_data),  # Convert to list for BSON
                },
            }
            try:
                bson_data = encode(publish_msg)
                print(f"Publishing binary data: {len(bson_data)} bytes BSON message")
                ws.send(bson_data, websocket.ABNF.OPCODE_BINARY)

                # Store publish test result
                self.results["tests"].append(
                    {
                        "test": "binary_publish_bson",
                        "status": "success",
                        "message": f"Published {len(test_binary_data)} bytes of binary data via BSON",
                        "bson_message_size": len(bson_data),
                        "original_data_size": len(test_binary_data),
                    }
                )
            except Exception as e:
                print(f"Error publishing binary data: {e}")
                self.results["tests"].append(
                    {"test": "binary_publish_bson", "status": "error", "error": str(e)}
                )

            # Set timeout for test completion
            time.sleep(15)
            if not self.test_completed and ws.sock and ws.sock.connected:
                print("Test timeout reached, closing connection...")
                print(
                    f'Messages received - Chatter: {self.message_count["chatter"]}, PointCloud: {self.message_count["pointcloud"]}'
                )
                print(
                    f'Validation status - Chatter: {self.validation_results["chatter"]}, PointCloud: {self.validation_results["pointcloud"]}'
                )
                if "overall_status" not in self.results:
                    self.results["overall_status"] = "TIMEOUT"
                ws.close()

        # Run subscriptions in a separate thread
        threading.Thread(target=send_subscriptions, daemon=True).start()

    def save_results(self):
        """Save test results to file"""
        import json

        # Add PointCloud2 analysis summary to results
        if hasattr(self, "pointcloud_analyses") and self.pointcloud_analyses:
            self.results["pointcloud_data_analysis"] = {
                "total_analyzed": len(self.pointcloud_analyses),
                "analyses": self.pointcloud_analyses,
                "summary": self.generate_analysis_summary(),
            }

        os.makedirs(RESULTS_DIR, exist_ok=True)
        timestamp = int(time.time() * 1000)
        filename = f"{RESULTS_DIR}/test-results-bson-{timestamp}.json"

        with open(filename, "w") as f:
            json.dump(self.results, f, indent=2)

        print(f"Results saved to: {filename}")

    def generate_analysis_summary(self):
        """Generate summary of PointCloud2 data analyses"""
        if not hasattr(self, "pointcloud_analyses") or not self.pointcloud_analyses:
            return {"error": "No analyses available"}

        formats = {}
        total_size = 0

        for analysis in self.pointcloud_analyses:
            format_type = analysis.get("format", "unknown")
            formats[format_type] = formats.get(format_type, 0) + 1
            total_size += analysis.get("size", 0)

        avg_size = total_size / len(self.pointcloud_analyses) if self.pointcloud_analyses else 0

        # Check if any data is base64 encoded
        has_base64 = any(a.get("format") == "base64" for a in self.pointcloud_analyses)
        has_bson_binary = any(a.get("format") == "bson_binary" for a in self.pointcloud_analyses)

        return {
            "format_distribution": formats,
            "average_data_size": avg_size,
            "total_messages_analyzed": len(self.pointcloud_analyses),
            "contains_base64": has_base64,
            "contains_bson_binary": has_bson_binary,
            "mode": "BSON-only",
            "encoding_efficiency": (
                "INEFFICIENT" if has_base64 else "EFFICIENT" if has_bson_binary else "UNKNOWN"
            ),
        }

    def run_test(self):
        """Run the integration test"""
        # For BSON mode testing, we'll send BSON messages to the regular endpoint
        # The server should be able to handle both JSON and BSON on the same endpoint
        self.ws = websocket.WebSocketApp(
            ROSBRIDGE_URL,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )

        self.ws.run_forever()


if __name__ == "__main__":
    test = ROSBridgeBSONModeBSONTest()
    test.run_test()
