# ROS 2 rosbridge Integration Tests

This directory contains integration tests for rosbridge_suite with BSON support.

## Overview

The integration tests verify:
- JSON mode subscription and service calls
- BSON mode subscription and service calls
- Compatibility with various ROS 2 message types (String, PointCloud2)
- Service functionality (SetBool, AddTwoInts)

## Prerequisites

- Docker and Docker Compose
- Built debian package in `../../debian-packages/`

## Running Tests

1. Build the debian package for current architecture:
   ```bash
   ./build-deb.sh
   ```

2. Start the test environment:
   ```bash
   docker-compose up --build
   ```

3. Check test results:
   ```bash
   ls -la results/
   ```

## Test Structure

- `compose.yml` - Docker Compose configuration
- `scripts/` - ROS 2 nodes for testing
  - `pointcloud2_publisher.py` - Publishes PointCloud2 messages
  - `echo_service.py` - Provides test services
- `client/` - JavaScript test client
  - `test-json.js` - Tests JSON mode
  - `test-bson.js` - Tests BSON mode
  - `test-all.js` - Runs all tests
- `results/` - Test results (created during test execution)

## Services

1. **ros-master** - Base ROS 2 environment
2. **chatter-talker** - Publishes string messages to `/chatter`
3. **pointcloud2-publisher** - Publishes PointCloud2 to `/pointcloud`
4. **echo-service** - Provides `/echo_set_bool` and `/echo_add_two_ints` services
5. **rosbridge-server** - rosbridge with BSON support
6. **test-client** - Runs integration tests

## Expected Results

Each test run generates:
- `test-results-json-*.json` - JSON mode test results
- `test-results-bson-*.json` - BSON mode test results
- `test-summary.json` - Overall test summary

Tests verify:
- Successful WebSocket connection
- Message subscription (chatter, pointcloud)
- Service calls and responses
- BSON serialization/deserialization