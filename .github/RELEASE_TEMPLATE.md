# ROS 2 rosbridge_suite with BSON support

This release contains Debian packages for ROS 2 Humble with BSON serialization support.

## 📦 Download & Installation

**Quick Installation**:
1. Download the appropriate package for your architecture from the Assets section below
2. Extract and install following the [detailed installation guide](https://github.com/aptpod/rosbridge_suite/blob/ros2/FORK_README.md#-インストール使用方法)

## 🚀 Key Features

- **BSON Support**: Enhanced binary serialization for improved performance with large payloads
- **Multi-Architecture**: Support for amd64 and arm64 systems
- **Backward Compatible**: Maintains full compatibility with existing rosbridge clients

## 📋 Supported Architectures

- **amd64**: Standard x86_64 Linux systems
- **arm64**: ARM64 systems (Raspberry Pi 4, Apple Silicon, etc.)

## 📖 Documentation

For comprehensive documentation, installation instructions, and usage examples, please refer to:

**→ [Complete Setup Guide (FORK_README.md)](https://github.com/aptpod/rosbridge_suite/blob/ros2/FORK_README.md)**

This guide includes:
- Detailed installation steps
- BSON mode configuration
- Performance optimization tips
- Troubleshooting information
- Version compatibility matrix

## 🔧 Quick Start

```bash
# Install the package (see FORK_README.md for dependencies)
sudo apt install -y ./ros-humble-rosbridge-suite_*.deb

# Standard JSON mode (default)
ros2 launch rosbridge_server rosbridge_websocket_launch.xml

# BSON-only mode for enhanced performance
ros2 launch rosbridge_server rosbridge_websocket_launch.xml bson_only_mode:=true
```

WebSocket server will be available at `ws://localhost:9090`

## 💬 Support

- **Issues & Questions**: [GitHub Issues](https://github.com/aptpod/rosbridge_suite/issues)
- **Documentation**: [FORK_README.md](https://github.com/aptpod/rosbridge_suite/blob/ros2/FORK_README.md)
- **Original Project**: [RobotWebTools/rosbridge_suite](https://github.com/RobotWebTools/rosbridge_suite)
