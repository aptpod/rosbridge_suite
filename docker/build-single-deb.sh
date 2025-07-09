#!/bin/bash
# Build script for creating a single Debian package of rosbridge_suite with BSON support

set -e

echo "Starting single Debian package build for rosbridge_suite..."

# Source ROS environment
source /opt/ros/humble/setup.bash

# Initialize rosdep
if [ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]; then
    echo "Initializing rosdep..."
    rosdep init
fi
rosdep update

# Copy source code if mounted from host
if [ -d "/source" ]; then
    echo "Copying source code from /source..."
    cp -r /source/* /workspace/

    # Debug: Check if BSON modifications exist in copied source
    echo "=== DEBUG: Checking BSON modifications in copied source ==="
    if [ -f "/workspace/rosbridge_server/src/rosbridge_server/websocket_handler.py" ]; then
        echo "websocket_handler.py found, checking for BSON modifications..."
        if grep -q "bson_only_mode" /workspace/rosbridge_server/src/rosbridge_server/websocket_handler.py; then
            echo "✓ BSON modifications found in source"
            echo "Line with bson_only_mode:"
            grep -n "bson_only_mode" /workspace/rosbridge_server/src/rosbridge_server/websocket_handler.py | head -3
        else
            echo "✗ BSON modifications NOT found in source"
        fi

        echo "Checking for 'BSON ONLY MODE' comment:"
        if grep -q "BSON ONLY MODE" /workspace/rosbridge_server/src/rosbridge_server/websocket_handler.py; then
            echo "✓ 'BSON ONLY MODE' comment found"
            grep -A 2 -B 2 "BSON ONLY MODE" /workspace/rosbridge_server/src/rosbridge_server/websocket_handler.py
        else
            echo "✗ 'BSON ONLY MODE' comment NOT found"
        fi
    else
        echo "✗ websocket_handler.py NOT found in copied source"
        echo "Available files in rosbridge_server:"
        find /workspace -name "websocket_handler.py" -type f 2>/dev/null || echo "No websocket_handler.py found anywhere"
    fi
    echo "=== END DEBUG ==="
fi

# Build all packages using colcon first
echo "Building all packages with colcon..."
cd /workspace
# Limit parallel jobs for emulated environments to prevent resource issues
PARALLEL_JOBS=$(nproc)
if [ "$PARALLEL_JOBS" -gt 2 ]; then
    PARALLEL_JOBS=2
fi

echo "Using $PARALLEL_JOBS parallel workers for colcon build"
echo "Starting colcon build at $(date)"
colcon build --parallel-workers $PARALLEL_JOBS --cmake-args -DCMAKE_BUILD_TYPE=Release --event-handlers console_direct+
echo "Colcon build completed at $(date)"

# Debug: Check if BSON modifications exist in built packages
echo "=== DEBUG: Checking BSON modifications in built packages ==="
if [ -d "install" ]; then
    echo "Looking for websocket_handler.py in install directory..."
    BUILT_WEBSOCKET_FILE=$(find install -name "websocket_handler.py" -type f | head -1)
    if [ -n "$BUILT_WEBSOCKET_FILE" ]; then
        echo "Found built websocket_handler.py at: $BUILT_WEBSOCKET_FILE"

        if grep -q "bson_only_mode" "$BUILT_WEBSOCKET_FILE"; then
            echo "✓ BSON modifications found in built package"
            echo "Lines with bson_only_mode:"
            grep -n "bson_only_mode" "$BUILT_WEBSOCKET_FILE" | head -3
        else
            echo "✗ BSON modifications NOT found in built package"
        fi

        if grep -q "BSON ONLY MODE" "$BUILT_WEBSOCKET_FILE"; then
            echo "✓ 'BSON ONLY MODE' comment found in built package"
            grep -A 2 -B 2 "BSON ONLY MODE" "$BUILT_WEBSOCKET_FILE"
        else
            echo "✗ 'BSON ONLY MODE' comment NOT found in built package"
            echo "Showing on_message method from built file:"
            grep -A 10 "def on_message" "$BUILT_WEBSOCKET_FILE" || echo "on_message method not found"
        fi
    else
        echo "✗ websocket_handler.py NOT found in install directory"
        echo "Files in install directory:"
        find install -name "*.py" | grep -i websocket || echo "No websocket-related files found"
    fi
else
    echo "✗ install directory not found"
fi
echo "=== END DEBUG ==="

# Generate a single Debian package from the install directory
echo "Creating unified Debian package..."
cd /workspace

# Create debian directory structure matching standard ROS installation
mkdir -p debian/DEBIAN
mkdir -p debian/opt/ros/humble

# Copy built files to standard ROS locations, reorganizing structure
echo "Copying files to standard ROS structure..."

# Use a more systematic approach to copy and reorganize files
for pkg_dir in install/*/; do
    if [ -d "$pkg_dir" ]; then
        pkg_name=$(basename "$pkg_dir")
        echo "Processing package: $pkg_name"

        # Only copy from package/local/* to /opt/ros/humble/*
        if [ -d "$pkg_dir/local" ]; then
            # Handle Python packages: convert dist-packages to site-packages
            if [ -d "$pkg_dir/local/lib/python3.10/dist-packages" ]; then
                mkdir -p debian/opt/ros/humble/lib/python3.10/site-packages
                cp -r "$pkg_dir/local/lib/python3.10/dist-packages"/* debian/opt/ros/humble/lib/python3.10/site-packages/ 2>/dev/null || true
            fi

            # Handle share directory
            if [ -d "$pkg_dir/local/share" ]; then
                mkdir -p debian/opt/ros/humble/share
                cp -r "$pkg_dir/local/share"/* debian/opt/ros/humble/share/ 2>/dev/null || true
            fi

            # Handle bin directory
            if [ -d "$pkg_dir/local/bin" ]; then
                mkdir -p debian/opt/ros/humble/bin
                cp -r "$pkg_dir/local/bin"/* debian/opt/ros/humble/bin/ 2>/dev/null || true
                # Make executables executable
                find debian/opt/ros/humble/bin -type f -exec chmod +x {} \;
            fi

            # Handle other lib files (excluding python3.10 which we handled above)
            if [ -d "$pkg_dir/local/lib" ]; then
                for item in "$pkg_dir/local/lib"/*; do
                    if [ -d "$item" ] && [ "$(basename "$item")" != "python3.10" ]; then
                        mkdir -p debian/opt/ros/humble/lib
                        cp -r "$item" debian/opt/ros/humble/lib/ 2>/dev/null || true
                    elif [ -f "$item" ]; then
                        mkdir -p debian/opt/ros/humble/lib
                        cp "$item" debian/opt/ros/humble/lib/ 2>/dev/null || true
                    fi
                done
            fi

            # Handle standard ROS 2 lib directory (critical for .so files)
            if [ -d "$pkg_dir/lib" ]; then
                mkdir -p debian/opt/ros/humble/lib
                cp -r "$pkg_dir/lib"/* debian/opt/ros/humble/lib/ 2>/dev/null || true
                echo "Copied standard lib files for $pkg_name"
            fi
        fi
    fi
done

# Copy essential ROS 2 package metadata files
echo "Copying ROS 2 package metadata..."
for pkg_dir in install/*/; do
    if [ -d "$pkg_dir" ]; then
        pkg_name=$(basename "$pkg_dir")

        # Copy package.xml files for ROS 2 package discovery
        if [ -f "/workspace/${pkg_name}/package.xml" ]; then
            mkdir -p "debian/opt/ros/humble/share/${pkg_name}"
            cp "/workspace/${pkg_name}/package.xml" "debian/opt/ros/humble/share/${pkg_name}/"
            echo "Copied package.xml for $pkg_name"
        fi

        # Copy CMakeLists.txt if exists
        if [ -f "/workspace/${pkg_name}/CMakeLists.txt" ]; then
            mkdir -p "debian/opt/ros/humble/share/${pkg_name}"
            cp "/workspace/${pkg_name}/CMakeLists.txt" "debian/opt/ros/humble/share/${pkg_name}/"
        fi

        # Copy launch files if they exist
        if [ -d "/workspace/${pkg_name}/launch" ]; then
            mkdir -p "debian/opt/ros/humble/share/${pkg_name}/launch"
            cp -r "/workspace/${pkg_name}/launch"/* "debian/opt/ros/humble/share/${pkg_name}/launch/"
        fi

        # Copy scripts if they exist
        if [ -d "/workspace/${pkg_name}/scripts" ]; then
            mkdir -p "debian/opt/ros/humble/share/${pkg_name}/scripts"
            cp -r "/workspace/${pkg_name}/scripts"/* "debian/opt/ros/humble/share/${pkg_name}/scripts/"
            chmod +x "debian/opt/ros/humble/share/${pkg_name}/scripts"/*
        fi

        # Create ROS 2 executable directory structure for Python packages
        if [ -d "/workspace/${pkg_name}/scripts" ]; then
            mkdir -p "debian/opt/ros/humble/lib/${pkg_name}"
            # Copy scripts as executables to lib directory for ROS 2 launch
            for script in "/workspace/${pkg_name}/scripts"/*; do
                if [ -f "$script" ]; then
                    script_name=$(basename "$script")
                    # Remove .py extension if present
                    exec_name="${script_name%.py}"
                    cp "$script" "debian/opt/ros/humble/lib/${pkg_name}/${exec_name}"
                    chmod +x "debian/opt/ros/humble/lib/${pkg_name}/${exec_name}"
                    echo "Created executable: /opt/ros/humble/lib/${pkg_name}/${exec_name}"
                fi
            done
        fi

        # Copy built install files (critical for ROS 2 package discovery)
        if [ -d "$pkg_dir/share" ]; then
            mkdir -p "debian/opt/ros/humble/share"
            cp -r "$pkg_dir/share"/* "debian/opt/ros/humble/share/" 2>/dev/null || true
        fi
    fi
done

# Create AMENT package index files (critical for ROS 2 package discovery)
echo "Creating AMENT package index..."
mkdir -p "debian/opt/ros/humble/share/ament_index/resource_index/packages"
mkdir -p "debian/opt/ros/humble/share/ament_index/resource_index/package_type"

# Register each package in the AMENT index
for pkg_dir in install/*/; do
    if [ -d "$pkg_dir" ]; then
        pkg_name=$(basename "$pkg_dir")

        # Create package resource marker
        touch "debian/opt/ros/humble/share/ament_index/resource_index/packages/${pkg_name}"

        # Create package type marker (assume python packages for most)
        if [ -f "/workspace/${pkg_name}/package.xml" ]; then
            if grep -q "<build_type>ament_python</build_type>" "/workspace/${pkg_name}/package.xml"; then
                echo "ament_python" > "debian/opt/ros/humble/share/ament_index/resource_index/package_type/${pkg_name}"
            elif grep -q "<build_type>ament_cmake</build_type>" "/workspace/${pkg_name}/package.xml"; then
                echo "ament_cmake" > "debian/opt/ros/humble/share/ament_index/resource_index/package_type/${pkg_name}"
            else
                echo "ament_python" > "debian/opt/ros/humble/share/ament_index/resource_index/package_type/${pkg_name}"
            fi
        else
            echo "ament_python" > "debian/opt/ros/humble/share/ament_index/resource_index/package_type/${pkg_name}"
        fi

        echo "Registered $pkg_name in AMENT index"
    fi
done

# Debug: Check if BSON modifications exist in package files
echo "=== DEBUG: Checking BSON modifications in package files ==="
PACKAGE_WEBSOCKET_FILE=$(find debian/opt/ros/humble -name "websocket_handler.py" -type f | head -1)
if [ -n "$PACKAGE_WEBSOCKET_FILE" ]; then
    echo "Found websocket_handler.py in package at: $PACKAGE_WEBSOCKET_FILE"

    if grep -q "bson_only_mode" "$PACKAGE_WEBSOCKET_FILE"; then
        echo "✓ BSON modifications found in package file"
        echo "Lines with bson_only_mode:"
        grep -n "bson_only_mode" "$PACKAGE_WEBSOCKET_FILE" | head -3
    else
        echo "✗ BSON modifications NOT found in package file"
    fi

    if grep -q "BSON ONLY MODE" "$PACKAGE_WEBSOCKET_FILE"; then
        echo "✓ 'BSON ONLY MODE' comment found in package file"
        grep -A 2 -B 2 "BSON ONLY MODE" "$PACKAGE_WEBSOCKET_FILE"
    else
        echo "✗ 'BSON ONLY MODE' comment NOT found in package file"
        echo "Showing on_message method from package file:"
        grep -A 10 "def on_message" "$PACKAGE_WEBSOCKET_FILE" || echo "on_message method not found"
    fi
else
    echo "✗ websocket_handler.py NOT found in package files"
    echo "Python files in package:"
    find debian/opt/ros/humble -name "*.py" | grep -i websocket || echo "No websocket-related files found"
    echo "Package structure debug:"
    echo "- dist-packages directory exists: $([ -d "debian/opt/ros/humble/lib/python3.10/dist-packages" ] && echo "Yes" || echo "No")"
    echo "- site-packages directory exists: $([ -d "debian/opt/ros/humble/lib/python3.10/site-packages" ] && echo "Yes" || echo "No")"
    echo "- lib/lib directory exists: $([ -d "debian/opt/ros/humble/lib/lib" ] && echo "Yes - THIS IS THE PROBLEM" || echo "No")"
    echo "Full directory structure:"
    find debian/opt/ros/humble -name "websocket_handler.py" -exec dirname {} \;
fi
echo "=== END DEBUG ==="

# Detect architecture
ARCH=$(dpkg --print-architecture)

# Determine version dynamically
if [ -n "$VERSION" ]; then
    # Use environment variable if set
    PACKAGE_VERSION="$VERSION"
    echo "Using version from environment: $PACKAGE_VERSION"
elif command -v git >/dev/null 2>&1 && git rev-parse --git-dir >/dev/null 2>&1; then
    # Try to get version from git tags
    GIT_VERSION=$(git describe --tags --always 2>/dev/null || echo "")
    if [ -n "$GIT_VERSION" ] && [ "$GIT_VERSION" != "$(git rev-parse --short HEAD)" ]; then
        PACKAGE_VERSION="$GIT_VERSION"
        echo "Using version from git: $PACKAGE_VERSION"
    else
        # Fallback to package.xml
        PACKAGE_VERSION=$(xmllint --xpath "string(//version)" /source/rosbridge_suite/package.xml 2>/dev/null || echo "2.0.1")
        echo "Using version from package.xml: $PACKAGE_VERSION"
    fi
else
    # Fallback to package.xml
    PACKAGE_VERSION=$(xmllint --xpath "string(//version)" /source/rosbridge_suite/package.xml 2>/dev/null || echo "2.0.1")
    echo "Using version from package.xml: $PACKAGE_VERSION"
fi

# Create control file
cat > debian/DEBIAN/control << EOF
Package: ros-humble-rosbridge-suite
Version: ${PACKAGE_VERSION}
Section: misc
Priority: optional
Architecture: ${ARCH}
Depends: ros-humble-ros-base, python3-twisted, python3-tornado, python3-autobahn, python3-pymongo, python3-pil
Maintainer: ROS Tooling <ros-tooling@foxglove.dev>
Description: ROS 2 rosbridge suite with BSON support
 The rosbridge suite contains packages for creating WebSocket bridges
 to ROS 2 systems. This version includes BSON serialization support
 for improved performance with binary data.
 .
 This package includes:
 - rosbridge_library (core functionality with BSON support)
 - rosbridge_server (WebSocket server)
 - rosapi (ROS API services)
 - Message definitions
EOF

# Create postinst script
cat > debian/DEBIAN/postinst << 'EOF'
#!/bin/bash
set -e

# Verify ROS setup still exists
if [ -f /opt/ros/humble/setup.bash ]; then
    echo "rosbridge_suite with BSON support has been installed."
    echo "The packages have been installed to the standard ROS 2 Humble locations:"
    echo "  Python packages: /opt/ros/humble/lib/python3.10/site-packages/"
    echo "  Launch files: /opt/ros/humble/share/"
    echo ""
    echo "To use it:"
    echo "  source /opt/ros/humble/setup.bash"
    echo "  ros2 launch rosbridge_server rosbridge_websocket_launch.xml"
else
    echo "Warning: ROS 2 Humble setup.bash not found. Please ensure ROS 2 Humble is installed."
fi

exit 0
EOF
chmod 755 debian/DEBIAN/postinst

# Create prerm script for cleanup
cat > debian/DEBIAN/prerm << 'EOF'
#!/bin/bash
set -e

# Note: Files are managed by dpkg and will be automatically removed
# No special cleanup needed as files are installed to standard locations

exit 0
EOF
chmod 755 debian/DEBIAN/prerm

# Build the .deb package
echo "Building .deb package for $ARCH..."
dpkg-deb --build debian ros-humble-rosbridge-suite_${ARCH}.deb

# Move to output directory
mv *.deb /output/

# Create simplified installation instructions
cat > /output/INSTALL.md << EOF
# Installation Instructions for rosbridge_suite with BSON support

## Prerequisites
- Ubuntu 22.04 (Jammy) with ROS 2 Humble installed

## Installation

\`\`\`bash
# Install dependencies first
sudo apt update
sudo apt install -y python3-twisted python3-tornado python3-autobahn python3-pymongo python3-pil

# Install the BSON-enabled rosbridge_suite package
sudo dpkg -i ./ros-humble-rosbridge-suite_*.deb
\`\`\`

## Usage

\`\`\`bash
# Source ROS environment
source /opt/ros/humble/setup.bash

# Run the WebSocket server with BSON support
ros2 launch rosbridge_server rosbridge_websocket_launch.xml
\`\`\`

The WebSocket server will be available at ws://localhost:9090 with BSON support enabled.

## Note

This package installs to the standard ROS 2 Humble locations:
- Python packages: \`/opt/ros/humble/lib/python3.10/site-packages/\`
- Launch files: \`/opt/ros/humble/share/\`

The package includes BSON serialization support for improved performance with binary data.

## Uninstallation

\`\`\`bash
sudo apt remove ros-humble-rosbridge-suite
\`\`\`
EOF

echo "Build completed. Single package created!"
ls -la /output/*.deb
