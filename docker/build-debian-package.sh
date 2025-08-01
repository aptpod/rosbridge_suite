#!/bin/bash
# Optimized build script for creating rosbridge_suite Debian package with BSON support

set -e

# ============================================================================
# Configuration and Globals
# ============================================================================
readonly WORKSPACE_DIR="/workspace"
readonly OUTPUT_DIR="/output"
readonly SOURCE_DIR="/source"
readonly ROS_DISTRO="humble"

# ============================================================================
# Utility Functions
# ============================================================================
log_info() {
    echo "[INFO] $1"
}

log_error() {
    echo "[ERROR] $1" >&2
}

log_debug() {
    echo "[DEBUG] $1"
}

# ============================================================================
# Environment Setup Functions
# ============================================================================
setup_ros_environment() {
    log_info "Setting up ROS $ROS_DISTRO environment..."
    
    # Source ROS environment, ignoring readonly variable warnings
    set +e
    source "/opt/ros/$ROS_DISTRO/setup.bash" 2>/dev/null || source "/opt/ros/$ROS_DISTRO/setup.bash"
    set -e
    
    if [ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]; then
        log_info "Initializing rosdep..."
        rosdep init
    fi
    rosdep update
}

copy_source_code() {
    if [ ! -d "$SOURCE_DIR" ]; then
        log_error "Source directory $SOURCE_DIR not found"
        exit 1
    fi
    
    log_info "Copying source code from $SOURCE_DIR..."
    cp -r "$SOURCE_DIR"/* "$WORKSPACE_DIR"/
}

# ============================================================================
# Build Verification Functions
# ============================================================================
verify_bson_modifications() {
    local websocket_file="$WORKSPACE_DIR/rosbridge_server/src/rosbridge_server/websocket_handler.py"
    
    log_debug "Verifying BSON modifications in source..."
    if [ ! -f "$websocket_file" ]; then
        log_error "websocket_handler.py not found at expected location"
        return 1
    fi
    
    if grep -q "bson_only_mode" "$websocket_file"; then
        log_info "✓ BSON modifications verified in source"
        return 0
    else
        log_error "✗ BSON modifications NOT found in source"
        return 1
    fi
}

verify_built_bson_modifications() {
    log_debug "Verifying BSON modifications in built packages..."
    local built_websocket_file
    built_websocket_file=$(find "$WORKSPACE_DIR/install" -name "websocket_handler.py" -type f | head -1)
    
    if [ -n "$built_websocket_file" ] && [ -f "$built_websocket_file" ]; then
        if grep -q "bson_only_mode" "$built_websocket_file"; then
            log_info "✓ BSON modifications verified in built package"
            return 0
        else
            log_error "✗ BSON modifications NOT found in built package"
            return 1
        fi
    else
        log_error "✗ websocket_handler.py not found in built packages"
        return 1
    fi
}

# ============================================================================
# Build Functions  
# ============================================================================
build_packages() {
    log_info "Building packages with colcon..."
    cd "$WORKSPACE_DIR"
    
    local parallel_jobs
    parallel_jobs=$(nproc)
    if [ "$parallel_jobs" -gt 2 ]; then
        parallel_jobs=2
    fi
    
    log_info "Using $parallel_jobs parallel workers for colcon build"
    log_info "Starting colcon build at $(date)"
    
    colcon build \
        --parallel-workers "$parallel_jobs" \
        --cmake-args -DCMAKE_BUILD_TYPE=Release \
        --event-handlers console_direct+
    
    log_info "Colcon build completed at $(date)"
}

# ============================================================================
# Package Structure Functions
# ============================================================================
create_debian_structure() {
    log_info "Creating Debian package structure..."
    cd "$WORKSPACE_DIR"
    
    mkdir -p debian/DEBIAN
    mkdir -p "debian/opt/ros/$ROS_DISTRO"
    
    copy_built_files
    copy_package_metadata  
    create_ament_index
}

copy_built_files() {
    log_info "Copying built files to standard ROS structure..."
    
    # Process each package directory
    for pkg_dir in install/*/; do
        if [ ! -d "$pkg_dir" ]; then
            continue
        fi
        
        local pkg_name
        pkg_name=$(basename "$pkg_dir")
        log_debug "Processing package: $pkg_name"
        
        # Copy from package/local/* to debian/opt/ros/humble/*
        if [ -d "$pkg_dir/local" ]; then
            copy_python_packages "$pkg_dir"
            copy_share_directory "$pkg_dir"
            copy_bin_directory "$pkg_dir"
            copy_lib_files "$pkg_dir"
        fi
        
        # Copy standard ROS 2 lib directory
        if [ -d "$pkg_dir/lib" ]; then
            mkdir -p "debian/opt/ros/$ROS_DISTRO/lib"
            cp -r "$pkg_dir/lib"/* "debian/opt/ros/$ROS_DISTRO/lib/" 2>/dev/null || true
            log_debug "Copied standard lib files for $pkg_name"
        fi
    done
}

copy_python_packages() {
    local pkg_dir="$1"
    
    if [ -d "$pkg_dir/local/lib/python3.10/dist-packages" ]; then
        mkdir -p "debian/opt/ros/$ROS_DISTRO/lib/python3.10/site-packages"
        cp -r "$pkg_dir/local/lib/python3.10/dist-packages"/* \
            "debian/opt/ros/$ROS_DISTRO/lib/python3.10/site-packages/" 2>/dev/null || true
    fi
}

copy_share_directory() {
    local pkg_dir="$1"
    
    if [ -d "$pkg_dir/local/share" ]; then
        mkdir -p "debian/opt/ros/$ROS_DISTRO/share"
        cp -r "$pkg_dir/local/share"/* \
            "debian/opt/ros/$ROS_DISTRO/share/" 2>/dev/null || true
    fi
}

copy_bin_directory() {
    local pkg_dir="$1"
    
    if [ -d "$pkg_dir/local/bin" ]; then
        mkdir -p "debian/opt/ros/$ROS_DISTRO/bin"
        cp -r "$pkg_dir/local/bin"/* \
            "debian/opt/ros/$ROS_DISTRO/bin/" 2>/dev/null || true
        find "debian/opt/ros/$ROS_DISTRO/bin" -type f -exec chmod +x {} \;
    fi
}

copy_lib_files() {
    local pkg_dir="$1"
    
    if [ -d "$pkg_dir/local/lib" ]; then
        for item in "$pkg_dir/local/lib"/*; do
            if [ -d "$item" ] && [ "$(basename "$item")" != "python3.10" ]; then
                mkdir -p "debian/opt/ros/$ROS_DISTRO/lib"
                cp -r "$item" "debian/opt/ros/$ROS_DISTRO/lib/" 2>/dev/null || true
            elif [ -f "$item" ]; then
                mkdir -p "debian/opt/ros/$ROS_DISTRO/lib"
                cp "$item" "debian/opt/ros/$ROS_DISTRO/lib/" 2>/dev/null || true
            fi
        done
    fi
}

copy_package_metadata() {
    log_info "Copying ROS 2 package metadata..."
    
    for pkg_dir in install/*/; do
        if [ ! -d "$pkg_dir" ]; then
            continue
        fi
        
        local pkg_name
        pkg_name=$(basename "$pkg_dir")
        
        copy_package_xml "$pkg_name"
        copy_cmake_files "$pkg_name"
        copy_launch_files "$pkg_name"
        copy_scripts "$pkg_name"
        copy_built_install_files "$pkg_dir"
    done
}

copy_package_xml() {
    local pkg_name="$1"
    
    if [ -f "$WORKSPACE_DIR/$pkg_name/package.xml" ]; then
        mkdir -p "debian/opt/ros/$ROS_DISTRO/share/$pkg_name"
        cp "$WORKSPACE_DIR/$pkg_name/package.xml" \
            "debian/opt/ros/$ROS_DISTRO/share/$pkg_name/"
        log_debug "Copied package.xml for $pkg_name"
    fi
}

copy_cmake_files() {
    local pkg_name="$1"
    
    if [ -f "$WORKSPACE_DIR/$pkg_name/CMakeLists.txt" ]; then
        mkdir -p "debian/opt/ros/$ROS_DISTRO/share/$pkg_name"
        cp "$WORKSPACE_DIR/$pkg_name/CMakeLists.txt" \
            "debian/opt/ros/$ROS_DISTRO/share/$pkg_name/"
    fi
}

copy_launch_files() {
    local pkg_name="$1"
    
    if [ -d "$WORKSPACE_DIR/$pkg_name/launch" ]; then
        mkdir -p "debian/opt/ros/$ROS_DISTRO/share/$pkg_name/launch"
        cp -r "$WORKSPACE_DIR/$pkg_name/launch"/* \
            "debian/opt/ros/$ROS_DISTRO/share/$pkg_name/launch/"
    fi
}

copy_scripts() {
    local pkg_name="$1"
    
    if [ -d "$WORKSPACE_DIR/$pkg_name/scripts" ]; then
        mkdir -p "debian/opt/ros/$ROS_DISTRO/share/$pkg_name/scripts"
        cp -r "$WORKSPACE_DIR/$pkg_name/scripts"/* \
            "debian/opt/ros/$ROS_DISTRO/share/$pkg_name/scripts/"
        chmod +x "debian/opt/ros/$ROS_DISTRO/share/$pkg_name/scripts"/*
        
        # Create ROS 2 executable directory structure
        mkdir -p "debian/opt/ros/$ROS_DISTRO/lib/$pkg_name"
        for script in "$WORKSPACE_DIR/$pkg_name/scripts"/*; do
            if [ -f "$script" ]; then
                local script_name
                script_name=$(basename "$script")
                local exec_name="${script_name%.py}"
                cp "$script" "debian/opt/ros/$ROS_DISTRO/lib/$pkg_name/$exec_name"
                chmod +x "debian/opt/ros/$ROS_DISTRO/lib/$pkg_name/$exec_name"
                log_debug "Created executable: /opt/ros/$ROS_DISTRO/lib/$pkg_name/$exec_name"
            fi
        done
    fi
}

copy_built_install_files() {
    local pkg_dir="$1"
    
    if [ -d "$pkg_dir/share" ]; then
        mkdir -p "debian/opt/ros/$ROS_DISTRO/share"
        cp -r "$pkg_dir/share"/* "debian/opt/ros/$ROS_DISTRO/share/" 2>/dev/null || true
    fi
}

create_ament_index() {
    log_info "Creating AMENT package index..."
    mkdir -p "debian/opt/ros/$ROS_DISTRO/share/ament_index/resource_index/packages"
    mkdir -p "debian/opt/ros/$ROS_DISTRO/share/ament_index/resource_index/package_type"
    
    for pkg_dir in install/*/; do
        if [ ! -d "$pkg_dir" ]; then
            continue
        fi
        
        local pkg_name
        pkg_name=$(basename "$pkg_dir")
        
        # Create package resource marker
        touch "debian/opt/ros/$ROS_DISTRO/share/ament_index/resource_index/packages/$pkg_name"
        
        # Determine and set package type
        local package_type="ament_python"  # default
        if [ -f "$WORKSPACE_DIR/$pkg_name/package.xml" ]; then
            if grep -q "<build_type>ament_cmake</build_type>" "$WORKSPACE_DIR/$pkg_name/package.xml"; then
                package_type="ament_cmake"
            fi
        fi
        
        echo "$package_type" > "debian/opt/ros/$ROS_DISTRO/share/ament_index/resource_index/package_type/$pkg_name"
        log_debug "Registered $pkg_name as $package_type in AMENT index"
    done
}

# ============================================================================
# Version and Package Creation Functions
# ============================================================================
determine_package_version() {
    if [ -n "$VERSION" ]; then
        PACKAGE_VERSION="$VERSION"
        log_info "Using version from environment: $PACKAGE_VERSION"
    elif command -v git >/dev/null 2>&1 && git rev-parse --git-dir >/dev/null 2>&1; then
        local git_version
        git_version=$(git describe --tags --always 2>/dev/null || echo "")
        if [ -n "$git_version" ] && [ "$git_version" != "$(git rev-parse --short HEAD)" ]; then
            PACKAGE_VERSION="$git_version"
            log_info "Using version from git: $PACKAGE_VERSION"
        else
            PACKAGE_VERSION=$(xmllint --xpath "string(//version)" "$SOURCE_DIR/rosbridge_suite/package.xml" 2>/dev/null || echo "2.0.1")
            log_info "Using version from package.xml: $PACKAGE_VERSION"
        fi
    else
        PACKAGE_VERSION=$(xmllint --xpath "string(//version)" "$SOURCE_DIR/rosbridge_suite/package.xml" 2>/dev/null || echo "2.0.1")
        log_info "Using version from package.xml: $PACKAGE_VERSION"
    fi
}

create_control_file() {
    local arch="$1"
    local template_file="$SOURCE_DIR/.github/templates/debian-control.template"
    
    if [ ! -f "$template_file" ]; then
        log_error "Debian control template not found at $template_file"
        log_error "This file is required for generating control file."
        exit 1
    fi
    
    log_debug "Creating control file from template..."
    sed "s/ROS_DISTRO_PLACEHOLDER/$ROS_DISTRO/g; s/VERSION_PLACEHOLDER/$PACKAGE_VERSION/g; s/ARCH_PLACEHOLDER/$arch/g" \
        "$template_file" > debian/DEBIAN/control
}

create_postinst_script() {
    local template_file="$SOURCE_DIR/.github/templates/postinst.template"
    
    if [ ! -f "$template_file" ]; then
        log_error "PostInst template not found at $template_file"
        log_error "This file is required for generating postinst script."
        exit 1
    fi
    
    log_debug "Creating postinst script from template..."
    sed "s/ROS_DISTRO_PLACEHOLDER/$ROS_DISTRO/g" \
        "$template_file" > debian/DEBIAN/postinst
    chmod 755 debian/DEBIAN/postinst
}

create_prerm_script() {
    local template_file="$SOURCE_DIR/.github/templates/prerm.template"
    
    if [ ! -f "$template_file" ]; then
        log_error "PreRM template not found at $template_file"
        log_error "This file is required for generating prerm script."
        exit 1
    fi
    
    log_debug "Creating prerm script from template..."
    cp "$template_file" debian/DEBIAN/prerm
    chmod 755 debian/DEBIAN/prerm
}

create_debian_package() {
    log_info "Building Debian package..."
    local arch
    arch=$(dpkg --print-architecture)
    
    create_control_file "$arch"
    create_postinst_script
    create_prerm_script
    
    dpkg-deb --build debian "ros-$ROS_DISTRO-rosbridge-suite_$arch.deb"
    mv ./*.deb "$OUTPUT_DIR"/
}

create_install_documentation() {
    local template_file="$SOURCE_DIR/.github/INSTALL_TEMPLATE.md"
    
    if [ ! -f "$template_file" ]; then
        log_error "INSTALL_TEMPLATE.md not found at $template_file"
        log_error "This file is required for generating installation instructions."
        exit 1
    fi
    
    log_info "Creating INSTALL.md from template..."
    sed "s/TAG_PLACEHOLDER/$PACKAGE_VERSION/g; s/VERSION_PLACEHOLDER/$PACKAGE_VERSION/g" \
        "$template_file" > "$OUTPUT_DIR/INSTALL.md"
}

# ============================================================================
# Main Execution Function
# ============================================================================
main() {
    log_info "Starting Debian package build for rosbridge_suite with BSON support..."
    
    # Environment setup
    setup_ros_environment
    copy_source_code
    
    # Build verification
    verify_bson_modifications
    
    # Package building
    build_packages
    verify_built_bson_modifications
    
    # Package creation
    create_debian_structure
    determine_package_version
    create_debian_package
    create_install_documentation
    
    log_info "Build completed successfully!"
    log_info "Generated packages:"
    ls -la "$OUTPUT_DIR"/*.deb
}

# ============================================================================
# Script Entry Point
# ============================================================================
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi