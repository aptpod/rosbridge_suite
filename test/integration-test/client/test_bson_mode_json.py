#!/usr/bin/env python3

import json
import os
import sys
import threading
import time
from datetime import datetime

import websocket

ROSBRIDGE_URL = os.environ.get("ROSBRIDGE_URL_BSON", "ws://localhost:9091")
RESULTS_DIR = os.environ.get("RESULTS_DIR", "/results")

print("Starting BSON mode server JSON test (expecting failure)...")
print(f"Connecting to: {ROSBRIDGE_URL}")


class ROSBridgeBSONModeJSONTest:
    def __init__(self):
        self.results = {
            "mode": "BSON_Mode_JSON_ExpectFail",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "tests": [],
        }
        self.ws = None
        self.test_completed = False
        self.connection_closed = False

    def on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        print(f"Unexpected message received: {message}")
        # In BSON-only mode, JSON messages should not be processed
        self.results["tests"].append(
            {
                "test": "json_to_bson_only_server",
                "status": "unexpected_success",
                "message": "JSON message was processed when it should have been rejected",
            }
        )
        self.results["overall_status"] = "FAILED"
        self.test_completed = True
        ws.close()

    def on_error(self, ws, error):
        """Handle WebSocket errors"""
        print(f"WebSocket error (expected): {error}")
        self.results["tests"].append(
            {
                "test": "json_to_bson_only_server",
                "status": "expected_error",
                "error": str(error),
                "message": "JSON message correctly rejected by BSON-only server",
            }
        )

    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        print("Connection closed")
        self.connection_closed = True

        # If we haven't recorded any tests, it means the connection was rejected
        if not self.results["tests"]:
            self.results["tests"].append(
                {
                    "test": "json_to_bson_only_server",
                    "status": "expected_rejection",
                    "message": "JSON messages correctly rejected by BSON-only server",
                }
            )
            self.results["overall_status"] = "PASSED"
        elif not hasattr(self.results, "overall_status"):
            self.results["overall_status"] = "PASSED"

        self.save_results()

        # Exit with appropriate code
        if self.results.get("overall_status") == "PASSED":
            print("🎉 BSON mode JSON rejection test PASSED")
            sys.exit(0)
        else:
            print("💥 BSON-only JSON rejection test FAILED")
            sys.exit(1)

    def on_open(self, ws):
        """Handle WebSocket connection open"""
        print("Connected to BSON mode server, attempting to send JSON...")

        def send_json_messages():
            # Test: Send JSON message to BSON-only server (should fail)
            try:
                json_message = {
                    "op": "subscribe",
                    "topic": "/chatter",
                    "type": "std_msgs/msg/String",
                }
                json_data = json.dumps(json_message)
                print(f"Sending JSON message: {json_data}")
                ws.send(json_data)

                # Wait a bit for any response or error
                time.sleep(5)

                # If we get here without error, the test should fail
                if not self.test_completed and not self.connection_closed:
                    print("No error occurred - JSON message may have been accepted incorrectly")
                    self.results["tests"].append(
                        {
                            "test": "json_to_bson_only_server",
                            "status": "unexpected_success",
                            "message": "JSON message was accepted by BSON-only server",
                        }
                    )
                    self.results["overall_status"] = "FAILED"
                    self.test_completed = True
                    ws.close()

            except Exception as e:
                print(f"Expected error when sending JSON: {e}")
                self.results["tests"].append(
                    {
                        "test": "json_to_bson_only_server",
                        "status": "expected_error",
                        "error": str(e),
                        "message": "JSON message correctly rejected",
                    }
                )
                self.results["overall_status"] = "PASSED"
                self.test_completed = True
                ws.close()

        # Run in a separate thread
        threading.Thread(target=send_json_messages, daemon=True).start()

    def save_results(self):
        """Save test results to file"""
        os.makedirs(RESULTS_DIR, exist_ok=True)
        timestamp = int(time.time() * 1000)
        filename = f"{RESULTS_DIR}/test-results-bson-only-json-{timestamp}.json"

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
    test = ROSBridgeBSONModeJSONTest()
    test.run_test()
