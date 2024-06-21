#include "UtilityFunctions.h"
#include "Request.h"
#include <iostream>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <chrono>
#include <ctime>
#include <sstream>
#include <iomanip>
#include <signal.h>
#include <cstddef>

void log(const std::string &message)
{
    // Get the current time
    auto now = std::chrono::system_clock::now();
    std::time_t now_time = std::chrono::system_clock::to_time_t(now);

    // Convert to local time
    std::tm local_time;
    localtime_r(&now_time, &local_time);

    // Format the time
    std::ostringstream oss;
    oss << std::put_time(&local_time, "%Y-%m-%d %H:%M:%S");

    // Print the formatted time and message
    std::cout << "[" << oss.str() << "] INFO " << message << std::endl;
}

void wakeUpProcess(const Request& request)
{
    kill(request.sleepPid, SIGUSR1);
}

void wakeUpProcess(int pid)
{
    kill(pid, SIGUSR1);
}

void ensureFileExists(const std::string &filePath)
{
    size_t lastSlashPos = filePath.find_last_of('/');
    if (lastSlashPos != std::string::npos)
    {
        std::string dirPath = filePath.substr(0, lastSlashPos);
        struct stat sb;
        if (stat(dirPath.c_str(), &sb) != 0 || !S_ISDIR(sb.st_mode))
        {
            mkdir(dirPath.c_str(), 0755);
        }
    }

    int fd = open(filePath.c_str(), O_CREAT | O_WRONLY, 0644);
    if (fd != -1)
    {
        close(fd);
    }
}

int getCpuTempInt()
{
    const char *path = "/sys/class/thermal/thermal_zone0/temp";
    int fd = open(path, O_RDONLY);
    char buffer[2];
    ssize_t bytesRead = pread(fd, buffer, 2, 0);
    close(fd);
    return (buffer[0] - '0') * 10 + (buffer[1] - '0');
}

float getCpuTempFloat()
{
    const char *path = "/sys/class/thermal/thermal_zone0/temp";
    int fd = open(path, O_RDONLY);
    char buffer[5];
    ssize_t bytesRead = pread(fd, buffer, 5, 0);
    close(fd);
    int d = (buffer[0] - '0') * 10 + (buffer[1] - '0');
    int f = (buffer[2] - '0') * 100 + (buffer[2] - '0') * 10 + (buffer[3] - '0');
    return static_cast<float>(d) + (static_cast<float>(f) / 100);
}

time_t dateCompactToEpoch(const std::string &inputDate)
{
    std::tm tm = {};
    std::istringstream ss(inputDate);
    ss >> std::get_time(&tm, "%Y%m%d_%H%M%S");
    if (ss.fail())
    {
        return -1; // Error handling, could not parse the date
    }
    tm.tm_isdst = -1;               // Not set by get_time, should be set to -1
    time_t epochTime = timegm(&tm); // Use timegm to interpret tm as UTC
    return epochTime - 7200;        // Compensate for CEST +0200
}

std::string vectorToString(const std::vector<std::string>& vec) {
    std::ostringstream oss;
    for (size_t i = 0; i < vec.size(); ++i) {
        oss << vec[i];
        if (i < vec.size() - 1) {
            oss << ", ";
        }
    }
    return oss.str();
}

