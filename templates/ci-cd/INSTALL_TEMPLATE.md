# Installation Instructions for rosbridge_suite with BSON support

## Prerequisites
- Ubuntu 22.04 (Jammy) with ROS 2 Humble installed

## Installation

```bash
# Install dependencies first
sudo apt update
sudo apt install -y python3-twisted python3-tornado python3-autobahn python3-pymongo python3-pil

# Install the BSON-enabled rosbridge_suite package
sudo dpkg -i ./ros-humble-rosbridge-suite_*.deb
```

## Usage

```bash
# Source ROS environment
source /opt/ros/humble/setup.bash

# Run the WebSocket server with BSON support
ros2 launch rosbridge_server rosbridge_websocket_launch.xml
```

The WebSocket server will be available at ws://localhost:9090 with BSON support enabled.

## Note

This package installs to the standard ROS 2 Humble locations:
- Python packages: `/opt/ros/humble/lib/python3.10/site-packages/`
- Launch files: `/opt/ros/humble/share/`

The package includes BSON serialization support for improved performance with binary data.

## Uninstallation

```bash
sudo apt remove ros-humble-rosbridge-suite
```

## Version Information

- **Version**: VERSION_PLACEHOLDER
- **Build Date**: Generated automatically
- **Documentation**: See [FORK_README.md](https://github.com/aptpod/rosbridge_suite/blob/TAG_PLACEHOLDER/FORK_README.md)
- **Technical Details**: See [FORK_TECHNICAL.md](https://github.com/aptpod/rosbridge_suite/blob/TAG_PLACEHOLDER/FORK_TECHNICAL.md)
- **Developer Guide**: See [FORK_DEVELOPER.md](https://github.com/aptpod/rosbridge_suite/blob/TAG_PLACEHOLDER/FORK_DEVELOPER.md)

For additional support and documentation, visit the [project repository](https://github.com/aptpod/rosbridge_suite/tree/TAG_PLACEHOLDER).
