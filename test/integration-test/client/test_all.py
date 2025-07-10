#!/usr/bin/env python3

import json
import os
import subprocess  # nosec B404 - subprocess is used safely with controlled input
import sys
import time
from datetime import datetime

print("Running all integration tests...")

# Ensure results directory exists
RESULTS_DIR = os.environ.get("RESULTS_DIR", "/results")
os.makedirs(RESULTS_DIR, exist_ok=True)

def run_test(script_name):
    """Run a Python test script and return success status"""
    print(f"\n========== Running {script_name} ==========")

    try:
        result = subprocess.run(
            [sys.executable, script_name], capture_output=False, text=True
        )  # nosec B603 - script_name is controlled

        print(f"\n{script_name} exited with code {result.returncode}")
        return result.returncode == 0

    except Exception as e:
        print(f"Error running {script_name}: {e}")
        return False


def main():
    json_test_passed = False
    bson_test_passed = False

    try:
        # Run JSON test
        try:
            json_test_passed = run_test("test_json.py")
            if json_test_passed:
                print("✅ JSON test completed successfully")
            else:
                print("❌ JSON test failed")
        except Exception as error:
            print(f"❌ JSON test failed: {error}")

        # Wait a bit between tests
        print("\nWaiting 5 seconds before next test...")
        time.sleep(5)

        # Run BSON test
        try:
            bson_test_passed = run_test("test_bson.py")
            if bson_test_passed:
                print("✅ BSON test completed successfully")
            else:
                print("❌ BSON test failed")
        except Exception as error:
            print(f"❌ BSON test failed: {error}")

        print("\n========== All tests completed ==========")
        print(f'JSON Test: {"PASSED" if json_test_passed else "FAILED"}')
        print(f'BSON Test: {"PASSED" if bson_test_passed else "FAILED"}')

        # Generate summary report
        summary_report = {
            "test_run": datetime.utcnow().isoformat() + "Z",
            "tests_executed": [
                {"name": "test_json.py", "status": "PASSED" if json_test_passed else "FAILED"},
                {"name": "test_bson.py", "status": "PASSED" if bson_test_passed else "FAILED"},
            ],
            "overall_status": "PASSED" if (json_test_passed and bson_test_passed) else "FAILED",
        }

        with open(f"{RESULTS_DIR}/test-summary.json", "w") as f:
            json.dump(summary_report, f, indent=2)

        # List all result files
        print("\nGenerated result files:")
        try:
            files = os.listdir(RESULTS_DIR)
            for file in files:
                file_path = os.path.join(RESULTS_DIR, file)
                if os.path.isfile(file_path):
                    size = os.path.getsize(file_path)
                    print(f"  - {file} ({size} bytes)")
        except Exception as e:
            print(f"Error listing result files: {e}")

        # Exit with appropriate code
        if json_test_passed and bson_test_passed:
            print("\n🎉 All integration tests PASSED")
            sys.exit(0)
        else:
            print("\n💥 Some integration tests FAILED")
            sys.exit(1)

    except Exception as error:
        print(f"Test execution failed: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()