add_library(scheduler STATIC
    src/ConfigManager.cpp
    src/FileRequestSource.cpp
    src/Scheduler.cpp
    src/UtilityFunctions.cpp)

target_include_directories(scheduler PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    /usr/include
)

# Create the executable
add_executable(scheduler_app src/main.cpp)

# Link the scheduler library to the executable
target_link_libraries(scheduler_app PRIVATE scheduler)