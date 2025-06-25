#!/bin/sh

set -eu

# clean up previous build artifacts
rm -rf build
mkdir -p build && cd build && cmake .. && make

ctest --verbose ${@} 