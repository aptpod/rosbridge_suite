# Integration Tests

This directory contains integration tests for the rosbridge_suite with BSON support.

## Structure

```
integration-test/
├── compose.yml              # Docker Compose configuration
├── Dockerfile.rosbridge     # Rosbridge server with BSON support
├── Dockerfile.client        # Test client container
├── client/                  # Test client scripts
│   ├── test_json.py        # JSON mode tests
│   ├── test_bson.py        # BSON mode tests
│   └── test_all.py         # Test orchestrator
├── scripts/                # Helper scripts
│   ├── pointcloud2_publisher.py  # PointCloud2 message publisher
│   └── rosbridge-entrypoint.sh   # Rosbridge server entrypoint
└── results/                # Test results (generated)
```

## Running Tests

### Local Development

```bash
# From project root
cd test/integration-test

# Build and run tests
docker compose up --build --abort-on-container-exit test-client

# View logs
docker compose logs rosbridge-server
docker compose logs test-client

# Clean up
docker compose down
```

### Using the convenience script

```bash
cd test/integration-test
./run-tests.sh
```

## Test Architecture

The integration tests use Docker Compose to create a complete ROS 2 environment:

1. **ros-master**: Base ROS 2 Humble environment
2. **chatter-talker**: Publishes demo messages to `/chatter` topic
3. **pointcloud2-publisher**: Publishes PointCloud2 messages to `/pointcloud` topic  
4. **rosbridge-server**: Rosbridge WebSocket server with BSON support
5. **test-client**: Python test client that validates JSON and BSON modes

## Test Results

Results are saved to the `results/` directory:

- `test-results-json-*.json` - JSON mode test results
- `test-results-bson-*.json` - BSON mode test results
- `test-summary.json` - Overall test summary

Tests verify:
- Successful WebSocket connection
- Message subscription (chatter, pointcloud)
- Service calls and responses
- BSON serialization/deserialization