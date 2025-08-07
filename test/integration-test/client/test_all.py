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
    # Track test results
    test_results = {}

    # Define all tests to run
    tests = [
        "test_json_mode_json.py",  # JSON mode with JSON (should succeed)
        "test_json_mode_bson.py",  # JSON mode with BSON (should fail)
        "test_bson_mode_json.py",  # BSON mode with JSON (should fail)
        "test_bson_mode_bson.py",  # BSON mode with BSON (should succeed)
    ]

    try:
        for test_script in tests:
            try:
                print(f"\nWaiting 3 seconds before {test_script}...")
                time.sleep(3)

                test_passed = run_test(test_script)
                test_results[test_script] = test_passed

                if test_passed:
                    print(f"✅ {test_script} completed successfully")
                else:
                    print(f"❌ {test_script} failed")

            except Exception as error:
                print(f"❌ {test_script} failed: {error}")
                test_results[test_script] = False

        print("\n========== All tests completed ==========")

        # Display results
        for test, passed in test_results.items():
            status = "PASSED" if passed else "FAILED"
            print(f"{test}: {status}")

        # Generate summary report
        tests_executed = []
        for test, passed in test_results.items():
            tests_executed.append({"name": test, "status": "PASSED" if passed else "FAILED"})

        all_passed = all(test_results.values())

        summary_report = {
            "test_run": datetime.utcnow().isoformat() + "Z",
            "tests_executed": tests_executed,
            "overall_status": "PASSED" if all_passed else "FAILED",
            "test_descriptions": {
                "test_json_mode_json.py": "JSON mode server with JSON messages (expects success)",
                "test_json_mode_bson.py": "JSON mode server with BSON messages (expects failure)",
                "test_bson_mode_json.py": "BSON mode server with JSON messages (expects failure)",
                "test_bson_mode_bson.py": "BSON mode server with BSON messages (expects success)",
            },
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
        if all_passed:
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
