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

# Help function
show_help() {
    echo "Build Debian packages for rosbridge_suite with BSON support"
    echo ""
    echo "Usage: $0 [OPTION|ARCH]"
    echo ""
    echo "Options:"
    echo "  (no args)     Build for all architectures (amd64, arm64, armhf)"
    echo "  --current     Build for current architecture only (fast)"
    echo "  --help, -h    Show this help message"
    echo "  ARCH          Build for specific architecture (amd64, arm64, armhf)"
    echo ""
    echo "Examples:"
    echo "  $0                   # Build all architectures"
    echo "  $0 --current         # Build current architecture only"
    echo "  $0 amd64             # Build for amd64 only"
    echo "  $0 arm64             # Build for arm64 only"
    echo ""
    echo "Output: debian-packages/ros-humble-rosbridge-suite_<arch>.deb"
}

# Parse command line arguments
if [ $# -eq 0 ]; then
    # Default: all architectures
    ARCHITECTURES=("amd64" "arm64" "armhf")
    echo -e "${YELLOW}Building for all architectures (use --current for current architecture only)${NC}"
elif [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    show_help
    exit 0
elif [ "$1" = "--current" ]; then
    # Current architecture only
    CURRENT_ARCH=$(docker info --format '{{.Architecture}}')
    ARCHITECTURES=("$CURRENT_ARCH")
    echo -e "${YELLOW}Building for current architecture only: $CURRENT_ARCH${NC}"
else
    # Specific architecture
    ARCHITECTURES=("$1")
    echo -e "${YELLOW}Building for specified architecture: $1${NC}"
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
