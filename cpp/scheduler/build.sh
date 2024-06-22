#!/bin/bash

# Set the directories
# below are taken from env
#REPO_DIR=
#TMP_DIR="$REPO_DIR/tmp"
#BIN_DIR="$REPO_DIR/bin"

# Create directories if they do not exist
mkdir -p "$TMP_DIR"
mkdir -p "$BIN_DIR"
SCHEDULER_ROOT_DIR="$REPO_DIR/cpp/scheduler"

INCLUDE_DIR="$SCHEDULER_ROOT_DIR/include"
SRC_DIR="$SCHEDULER_ROOT_DIR/src"

echo "Compiling executables"

function cleanup_file() {
  local FILE="$1"
  local FILENAME="$(echo "$FILE" | rev | cut -d'/' -f 1 | rev)"
  local SHA_FILE="${FILENAME}.sha256"
  local O_FILE="${FILENAME}.o"
  rm "$TMP_DIR/$SHA_FILE" &> /dev/null
  rm "$TMP_DIR/$O_FILE" &> /dev/null
}

# Function to check if a file has changed
function has_changed() {
  local FILE="$1"
  local FILENAME="$(echo "$FILE" | rev | cut -d'/' -f 1 | rev)"
  local SHA_FILE="${FILENAME}.sha256"
  if [ ! -f "$TMP_DIR/$SHA_FILE" ] || [[ "$(sha256sum "$FILE" | cut -d ' ' -f 1)" != "$(cat "$TMP_DIR/$SHA_FILE")" ]]; then
    return 0
  else
    return 1
  fi
}

# Function to update the SHA256 checksum of a file
function update_sha() {
  local FILE="$1"
  local FILENAME="$(echo "$FILE" | rev | cut -d'/' -f 1 | rev)"
  local SHA_FILE="${FILENAME}.sha256"
  sha256sum "$FILE" | cut -d ' ' -f 1 > "$TMP_DIR/$SHA_FILE"
}

if [[ "$1" == "rebuild" ]]; then
  for F in "ConfigManager.cpp" "FileRequestSource.cpp" "Scheduler.cpp" "UtilityFunctions.cpp" "main.cpp"; do
    cleanup_file "$F"
  done
fi

# List of source files
SRC_FILES=("src/ConfigManager.cpp" "src/FileRequestSource.cpp" "src/Scheduler.cpp" "src/UtilityFunctions.cpp" "main.cpp")
OBJ_PATHS=()
CXX=g++
CXXFLAGS="-std=c++17 -w -I$INCLUDE_DIR -Ofast -march=native -flto -finline-functions -funroll-loops -ffast-math"

ANY_CHANGED=false
# Check each source file for changes and compile if necessary
for SRC_FILE in "${SRC_FILES[@]}"; do
  SRC_PATH="$SCHEDULER_ROOT_DIR/$SRC_FILE"

  FILENAME="$(echo "$SRC_FILE" | cut -d'/' -f 2)"
  OBJ_PATH="$TMP_DIR/${FILENAME%.cpp}.o"
  if has_changed "$SRC_PATH"; then
    ANY_CHANGED=true
    echo "Compiling $SRC_FILE"
    echo "COMMAND: $CXX $CXXFLAGS -c $SRC_PATH -o $OBJ_PATH"
    $CXX $CXXFLAGS -c "$SRC_PATH" -o "$OBJ_PATH"
    update_sha "$SRC_PATH"
  fi
  OBJ_PATHS+=("$OBJ_PATH")
done

if [[ "$ANY_CHANGED" == "true" ]]; then
  # Link object files into a single executable
  echo "Linking object files"
  echo "COMMAND: $CXX $CXXFLAGS -o $BIN_DIR/scheduler ${OBJ_PATHS[@]}"

  $CXX $CXXFLAGS -o "$BIN_DIR/scheduler" "${OBJ_PATHS[@]}"
else
  echo "Nothing changed"
fi
echo "Build completed. Executable is located at $BIN_DIR/scheduler"
