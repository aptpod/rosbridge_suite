#!/bin/bash

# Build Debian package for integration tests
# This is a simplified version that builds for the current architecture

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

# Ensure debian-packages directory exists
mkdir -p debian-packages

echo "Building for current architecture..."
./build-deb.sh

echo "Build complete. Debian packages available in: $PROJECT_ROOT/debian-packages/"
ls -la "$PROJECT_ROOT/debian-packages/"