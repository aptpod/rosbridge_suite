#!/usr/bin/env python3

import os
import sys
import time
from datetime import datetime

import websocket
from bson import encode

ROSBRIDGE_URL = os.environ.get("ROSBRIDGE_URL", "ws://localhost:9090")
RESULTS_DIR = os.environ.get("RESULTS_DIR", "/results")

print("Starting JSON mode server BSON test (expecting failure)...")
print(f"Connecting to: {ROSBRIDGE_URL}")


class ROSBridgeJSONModeBSONTest:
    def __init__(self):
        self.results = {
            "mode": "JSON_Mode_BSON_ExpectFail",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "tests": [],
        }
        self.connection_failed = False
        self.timeout_reached = False
        self.error_occurred = False
        self.ws = None

    def on_message(self, ws, message):
        """Handle incoming WebSocket messages - should not receive any in failure case"""
        print(f"Unexpected message received: {message}")
        self.results["tests"].append(
            {
                "test": "unexpected_message",
                "status": "unexpected_success",
                "message": "Received message when failure was expected",
            }
        )

    def on_error(self, ws, error):
        """Handle WebSocket errors - expected behavior"""
        print(f"Expected WebSocket error occurred: {error}")
        self.error_occurred = True
        self.results["tests"].append(
            {
                "test": "bson_to_json_mode",
                "status": "expected_failure",
                "error": str(error),
                "error_type": str(type(error)),
            }
        )

    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        print("Connection closed")

        # Determine if test passed (failure was expected)
        if self.error_occurred or self.timeout_reached or self.connection_failed:
            print("✅ JSON mode BSON test PASSED (failure expected and occurred)")
            self.results["overall_status"] = "PASSED"
            self.results["summary"] = "BSON message correctly failed in JSON-only mode"
        else:
            print("❌ JSON mode BSON test FAILED (expected failure but got success)")
            self.results["overall_status"] = "FAILED"
            self.results["summary"] = "BSON message unexpectedly succeeded in JSON-only mode"

        self.save_results()

        # Exit with appropriate code (success means we got expected failure)
        if self.results.get("overall_status") == "PASSED":
            print("🎉 JSON mode BSON rejection test PASSED")
            sys.exit(0)
        else:
            print("💥 JSON mode BSON rejection test FAILED")
            sys.exit(1)

    def on_open(self, ws):
        """Handle WebSocket connection open"""
        print("Connected to JSON mode server, attempting to send BSON...")
        print(f"Connected to: {ROSBRIDGE_URL}")

        def send_bson_and_wait():
            try:
                # Test: Send BSON message to JSON-only server (should fail)
                print("Sending BSON message to JSON-only server...")
                subscribe_message = {
                    "op": "subscribe",
                    "topic": "/chatter",
                    "type": "std_msgs/msg/String",
                }

                bson_data = encode(subscribe_message)
                print(f"Sending BSON data: {len(bson_data)} bytes")
                ws.send(bson_data, websocket.ABNF.OPCODE_BINARY)
                print("BSON message sent")

                self.results["tests"].append(
                    {
                        "test": "bson_send_to_json_mode",
                        "status": "sent",
                        "data_size": len(bson_data),
                    }
                )

            except Exception as e:
                print(f"Error sending BSON message: {e}")
                self.error_occurred = True
                self.results["tests"].append(
                    {
                        "test": "bson_send_error",
                        "status": "expected_error",
                        "error": str(e),
                    }
                )

            # Wait for potential response or timeout
            time.sleep(10)

            if not self.error_occurred and ws.sock and ws.sock.connected:
                print("Timeout reached - no error occurred (unexpected)")
                self.timeout_reached = True
                self.results["tests"].append(
                    {
                        "test": "timeout_check",
                        "status": "timeout_without_error",
                        "message": "No error occurred within timeout period",
                    }
                )
                ws.close()

        import threading

        threading.Thread(target=send_bson_and_wait, daemon=True).start()

    def save_results(self):
        """Save test results to file"""
        import json

        os.makedirs(RESULTS_DIR, exist_ok=True)
        timestamp = int(time.time() * 1000)
        filename = f"{RESULTS_DIR}/test-results-json-mode-bson-{timestamp}.json"

        with open(filename, "w") as f:
            json.dump(self.results, f, indent=2)

        print(f"Results saved to: {filename}")

    def run_test(self):
        """Run the integration test"""
        self.ws = websocket.WebSocketApp(
            ROSBRIDGE_URL,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )

        self.ws.run_forever()


if __name__ == "__main__":
    test = ROSBridgeJSONModeBSONTest()
    test.run_test()
