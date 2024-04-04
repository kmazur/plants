#!/bin/bash

echo "Compiling executables"

cd "$REPO_DIR/shell/scripts/audio/" || exit 1
gcc -o volume_aggregator volume_aggregator.c -Ofast -march=native -flto -finline-functions -funroll-loops -ffast-math
mv volume_aggregator "$BIN_DIR"


cd "$REPO_DIR/shell/scripts/video/" || exit 1
g++ -o light_level light_level.cpp `pkg-config --cflags --libs opencv4` -Ofast -march=native -flto -finline-functions -funroll-loops -ffast-math
mv light_level "$BIN_DIR"

cd "$REPO_DIR/shell/scripts/video/" || exit 1
g++ -std=c++17 -o motion_detector motion_detector.cpp `pkg-config --cflags --libs opencv4 lopencv_core lopencv_videoio lopencv_imgproc lopencv_highgui pthread` -Ofast -march=native -flto -finline-functions -funroll-loops -ffast-math
mv motion_detector "$BIN_DIR"

