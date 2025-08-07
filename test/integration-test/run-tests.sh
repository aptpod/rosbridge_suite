#!/bin/bash
set -e

echo "Integration Test Runner for rosbridge_suite with BSON support"
echo "============================================================="

# Build debian package
echo "Building debian package..."
./build-deb.sh

# Create results directory
mkdir -p results

# Test 1: JSON mode
echo -e "\n[1/2] Running JSON mode test..."
docker compose up --build --abort-on-container-exit --exit-code-from test-client

# Clean up
docker compose down

# Wait between tests
echo -e "\nWaiting 5 seconds before next test..."
sleep 5

# Test 2: BSON mode
echo -e "\n[2/2] Running BSON mode test..."
docker compose -f compose.yml -f compose-bson.yml up --build --abort-on-container-exit --exit-code-from test-client

# Clean up
docker compose down

echo -e "\n============================================================="
echo "All tests completed! Check results in ./results/"
ls -la results/
