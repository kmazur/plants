#!/bin/bash

echo "Compiling executables"

function has_changed() {
  local FILE="$1"
  local SHA_FILE="${FILE}.sha256"
  if [ ! -f "$TMP_DIR/$SHA_FILE" ] || [[ "$(cat "$TMP_DIR/$SHA_FILE")" != "$(sha256sum "$FILE" | cut -d ' ' -f 1)" ]]; then
    return 0
  else
    return 1
  fi
}

function update_sha() {
  local FILE="$1"
  local SHA_FILE="${FILE}.sha256"
  sha256sum "$FILE" | cut -d ' ' -f 1 > "$TMP_DIR/$SHA_FILE"
}


cd "$REPO_DIR/shell/scripts/audio/" || exit 1
if has_changed "volume_aggregator.c"; then
  echo "Compiling volume_aggregator"
  gcc -o volume_aggregator volume_aggregator.c -Ofast -march=native -flto -finline-functions -funroll-loops -ffast-math
  mv volume_aggregator "$BIN_DIR"
  update_sha "volume_aggregator.c"
fi



cd "$REPO_DIR/shell/scripts/video/" || exit 1
if has_changed "light_level.cpp"; then
  echo "Compiling light_level"
  g++ -o light_level light_level.cpp `pkg-config --cflags --libs opencv4` -Ofast -march=native -flto -finline-functions -funroll-loops -ffast-math
  mv light_level "$BIN_DIR"
  update_sha "light_level.cpp"
fi


cd "$REPO_DIR/shell/scripts/video/" || exit 1
if has_changed "motion_detector.cpp"; then
  echo "Compiling motion_detector"
  g++ -std=c++17 -o motion_detector motion_detector.cpp `pkg-config --cflags --libs opencv4` -pthread -Ofast -march=native -flto -finline-functions -funroll-loops -ffast-math
  mv motion_detector "$BIN_DIR"
  update_sha "motion_detector.cpp"
fi





