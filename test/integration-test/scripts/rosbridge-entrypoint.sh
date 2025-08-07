#!/bin/bash
set -e

# Source ROS environment
source /opt/ros/humble/setup.bash

# Check for bson_only_mode parameter
if [ "$BSON_ONLY_MODE" = "true" ]; then
    echo "Starting rosbridge server in BSON mode (BSON-only)..."
    echo "BSON_ONLY_MODE environment variable: $BSON_ONLY_MODE"
    export RCUTILS_LOGGING_BUFFERED_STREAM=1
    export RCUTILS_COLORIZED_OUTPUT=0
    exec ros2 launch rosbridge_server rosbridge_websocket_launch.xml bson_only_mode:=true log_level:=debug
else
    echo "Starting rosbridge server in JSON mode (JSON-only)..."
    echo "BSON_ONLY_MODE environment variable: $BSON_ONLY_MODE"
    export RCUTILS_LOGGING_BUFFERED_STREAM=1
    export RCUTILS_COLORIZED_OUTPUT=0
    exec ros2 launch rosbridge_server rosbridge_websocket_launch.xml bson_only_mode:=false log_level:=debug
fi
