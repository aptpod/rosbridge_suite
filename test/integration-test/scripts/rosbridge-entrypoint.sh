#!/bin/bash
set -e

# Source ROS environment
source /opt/ros/humble/setup.bash

# Check for bson_only_mode parameter
if [ "$BSON_ONLY_MODE" = "true" ]; then
    echo "Starting rosbridge server in BSON-only mode..."
    exec ros2 launch rosbridge_server rosbridge_websocket_launch.xml bson_only_mode:=true
else
    echo "Starting rosbridge server in standard (JSON) mode..."
    exec ros2 launch rosbridge_server rosbridge_websocket_launch.xml
fi