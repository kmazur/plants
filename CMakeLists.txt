cmake_minimum_required(VERSION 3.10)

# Set the project name and version
project(plants VERSION 1.0)

# Set the C++ standard
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF) # -std=c++11 instead of -std=gnu++11

add_subdirectory(cpp/scheduler)