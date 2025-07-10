#!/bin/bash
set -e

# Script to build debian package for current architecture
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "Building debian package for integration test..."
echo "Project root: $PROJECT_ROOT"

# Change to project root
cd "$PROJECT_ROOT"

# Build for current architecture only
echo "Building for current architecture..."
./build-deb.sh

echo "Build complete. Debian packages available in: $PROJECT_ROOT/debian-packages/"
ls -la "$PROJECT_ROOT/debian-packages/"