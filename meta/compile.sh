#!/bin/bash

echo "Compiling executables"

cd "$REPO_DIR/shell/scripts/audio/" || exit 1
gcc -o volume_aggregator volume_aggregator.c -O3 -march=native -flto
mv volume_aggregator "$BIN_DIR"


cd "$REPO_DIR/shell/scripts/video/" || exit 1
g++ -o light_level light_level.cpp `pkg-config --cflags --libs opencv4` -O3 -march=native -flto
mv light_level "$BIN_DIR"

cd "$REPO_DIR/shell/scripts/video/" || exit 1
g++ -o motion_detector motion_detector.cpp `pkg-config --cflags --libs opencv4` -O3 -march=native -flto
mv motion_detector "$BIN_DIR"