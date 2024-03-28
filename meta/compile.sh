#!/bin/bash

echo "Compiling executables"
cd "$REPO_DIR/shell/scripts/audio/" || exit 1

gcc -o volume_aggregator volume_aggregator.c -O3
mv volume_aggregator "$BIN_DIR"
