#!/bin/bash
# Build Debian packages for rosbridge_suite with BSON support
#
# For usage information, run: ./build-deb.sh --help

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Building rosbridge_suite Debian packages for all architectures...${NC}"

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Create output directory
OUTPUT_DIR="${SCRIPT_DIR}/debian-packages"
mkdir -p "${OUTPUT_DIR}"

# Supported architectures
SUPPORTED_ARCHITECTURES=("amd64" "arm64")

# Helper functions
list_architectures() {
    echo "Supported architectures:"
    for arch in "${SUPPORTED_ARCHITECTURES[@]}"; do
        echo "  - $arch"
    done
    echo ""
    echo "Current architecture: $(docker info --format '{{.Architecture}}' 2>/dev/null || uname -m)"
}

clean_artifacts() {
    echo -e "${YELLOW}Cleaning build artifacts...${NC}"
    rm -rf "${OUTPUT_DIR}"/*.deb
    rm -rf build/ install/ log/
    docker system prune -f --filter "label=rosbridge-build" 2>/dev/null || true
    echo -e "${GREEN}Cleaned build artifacts${NC}"
}

validate_architecture() {
    local arch="$1"
    for supported in "${SUPPORTED_ARCHITECTURES[@]}"; do
        if [ "$arch" = "$supported" ]; then
            return 0
        fi
    done
    return 1
}

# Help function
show_help() {
    echo "Build Debian packages for rosbridge_suite with BSON support"
    echo ""
    echo "Usage: $0 [OPTION|ARCH...]"
    echo ""
    echo "Options:"
    echo "  (no args)     Build for current architecture only (fast)"
    echo "  --all, -a     Build for all supported architectures (amd64, arm64)"
    echo "  --list        List supported architectures"
    echo "  --clean       Clean build artifacts before building"
    echo "  --help, -h    Show this help message"
    echo "  ARCH...       Build for specific architecture(s) (amd64, arm64)"
    echo ""
    echo "Examples:"
    echo "  $0                   # Build current architecture only"
    echo "  $0 --all             # Build all supported architectures"
    echo "  $0 -a                # Same as --all (short form)"
    echo "  $0 amd64             # Build for amd64 only"
    echo "  $0 arm64             # Build for arm64 only"
    echo "  $0 amd64 arm64       # Build for multiple architectures"
    echo "  $0 --clean --all     # Clean and build all architectures"
    echo ""
    echo "Supported architectures: amd64, arm64"
    echo "Output: debian-packages/ros-humble-rosbridge-suite_<arch>.deb"
}

# Parse command line arguments
ARCHITECTURES=()
CLEAN_BEFORE_BUILD=false

# Process arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_help
            exit 0
            ;;
        --all|-a)
            ARCHITECTURES=("${SUPPORTED_ARCHITECTURES[@]}")
            shift
            ;;
        --list)
            list_architectures
            exit 0
            ;;
        --clean)
            CLEAN_BEFORE_BUILD=true
            shift
            ;;
        --*)
            echo -e "${RED}Error: Unknown option $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
        *)
            # Architecture argument
            if validate_architecture "$1"; then
                ARCHITECTURES+=("$1")
            else
                echo -e "${RED}Error: Unsupported architecture '$1'${NC}"
                echo "Supported architectures: ${SUPPORTED_ARCHITECTURES[*]}"
                exit 1
            fi
            shift
            ;;
    esac
done

# Default to current architecture if no architectures specified
if [ ${#ARCHITECTURES[@]} -eq 0 ]; then
    CURRENT_ARCH=$(docker info --format '{{.Architecture}}' 2>/dev/null || uname -m)
    ARCHITECTURES=("$CURRENT_ARCH")
    echo -e "${YELLOW}Building for current architecture only: $CURRENT_ARCH${NC}"
else
    # Remove duplicates while preserving order
    UNIQUE_ARCHITECTURES=()
    for arch in "${ARCHITECTURES[@]}"; do
        if [[ ! " ${UNIQUE_ARCHITECTURES[*]} " =~ " $arch " ]]; then
            UNIQUE_ARCHITECTURES+=("$arch")
        fi
    done
    ARCHITECTURES=("${UNIQUE_ARCHITECTURES[@]}")
    echo -e "${YELLOW}Building for architectures: ${ARCHITECTURES[*]}${NC}"
fi

# Clean artifacts if requested
if [ "$CLEAN_BEFORE_BUILD" = true ]; then
    clean_artifacts
fi

# Build for each architecture
for ARCH in "${ARCHITECTURES[@]}"; do
    echo -e "${YELLOW}Building Docker image for architecture: ${ARCH}${NC}"

    # Build platform-specific image
    docker build \
        --platform "linux/${ARCH}" \
        -f "${SCRIPT_DIR}/docker/Dockerfile.debian-build" \
        -t "rosbridge-debian-builder:${ARCH}" \
        "${SCRIPT_DIR}"

    echo -e "${YELLOW}Running build for architecture: ${ARCH}${NC}"

    # Run build without platform specification (image is already platform-specific)
    docker run --rm \
        -v "${SCRIPT_DIR}:/source:ro" \
        -v "${OUTPUT_DIR}:/output" \
        "rosbridge-debian-builder:${ARCH}"

    echo -e "${GREEN}Completed build for ${ARCH}${NC}"
    echo ""
done

# List all generated packages
echo -e "${GREEN}All builds completed!${NC}"
echo -e "${GREEN}Generated packages:${NC}"
ls -la "${OUTPUT_DIR}"/*.deb

echo ""
echo -e "${YELLOW}Installation instructions:${NC}"
echo "  sudo apt install ${OUTPUT_DIR}/ros-humble-rosbridge-suite_*.deb"
