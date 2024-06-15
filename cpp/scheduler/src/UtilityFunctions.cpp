#include "UtilityFunctions.h"
#include <iostream>
#include <csignal>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <chrono>
#include <ctime>
#include <sstream>
#include <iomanip>

void log(const std::string& message) {
    std::cout << message << std::endl;
}

void wakeUpProcess(pid_t pid) {
    kill(pid, SIGUSR1);
}

void ensureFileExists(const std::string& filePath) {
    size_t lastSlashPos = filePath.find_last_of('/');
    if (lastSlashPos != std::string::npos) {
        std::string dirPath = filePath.substr(0, lastSlashPos);
        struct stat sb;
        if (stat(dirPath.c_str(), &sb) != 0 || !S_ISDIR(sb.st_mode)) {
            mkdir(dirPath.c_str(), 0755);
        }
    }

    int fd = open(filePath.c_str(), O_CREAT | O_WRONLY, 0644);
    if (fd != -1) {
        close(fd);
    }
}

int getCpuTempInt() {
    const char* path = "/sys/class/thermal/thermal_zone0/temp";
    int fd = open(path, O_RDONLY);
    char buffer[2];
    ssize_t bytesRead = pread(fd, buffer, 2, 0);
    close(fd);
    return (buffer[0] - '0') * 10 + (buffer[1] - '0');
}

time_t dateCompactToEpoch(const std::string& inputDate) {
    std::tm tm = {};
    std::istringstream ss(inputDate);
    ss >> std::get_time(&tm, "%Y%m%d_%H%M%S");
    if (ss.fail()) {
        return -1; // Error handling, could not parse the date
    }
    tm.tm_isdst = -1; // Not set by get_time, should be set to -1
    time_t epochTime = timegm(&tm); // Use timegm to interpret tm as UTC
    return epochTime - 7200; // Compensate for CEST +0200
}