#include "FileRequestProvider.h"
#include "UtilityFunctions.h"
#include "ConfigManager.h"
#include <fstream>
#include <sstream>
#include <algorithm>
#include <sys/file.h>
#include <unistd.h>
#include <ctime>

FileRequestProvider::FileRequestProvider(const std::string& filePath, size_t maxRequests)
    : filePath(filePath), maxRequests(maxRequests), requests(maxRequests) {}

const std::vector<Request>& FileRequestProvider::getRequests() const {
    requests.clear(); // Clear previous requests
    requests.resize(maxRequests); // Ensure the vector has the capacity for maxRequests
    std::ifstream infile(filePath);
    std::string line;
    size_t requestIndex = 0;

    while (std::getline(infile, line) && requestIndex < maxRequests) {
        if (line.empty()) {
            continue;
        }
        parseLine(line, requests[requestIndex]);
        ++requestIndex;
    }

    requests.resize(requestIndex); // Adjust the size to the number of actual requests read
    return requests;
}

void FileRequestProvider::parseLine(const std::string& line, Request& request) const {
    std::istringstream ss(line);
    std::string process, tokensStr, pidStr, datetime;

    std::getline(ss, process, '=');
    std::getline(ss, tokensStr, ':');
    std::getline(ss, pidStr, ':');
    std::getline(ss, datetime);

    request.process = process;
    request.requestedTokens = std::stod(tokensStr);
    request.sleepPid = std::stoi(pidStr);
    request.requestTimestamp = dateCompactToEpoch(datetime);
    request.waitTime = std::time(nullptr) - request.requestTimestamp;
}

void FileRequestProvider::markRequestFulfilled(const std::string& process) {
    removeRequestLine(process);
}

void FileRequestProvider::removeRequestLine(const std::string& process) {
    int fd = open(filePath.c_str(), O_RDWR);
    if (fd == -1) {
        return; // Error handling, could not open the file
    }

    if (flock(fd, LOCK_EX) == -1) {
        close(fd);
        return; // Error handling, could not lock the file
    }

    std::ostringstream tempContent;
    std::ifstream infile(filePath);
    std::string line;

    while (std::getline(infile, line)) {
        if (line.substr(0, line.find('=')) != process) {
            tempContent << line << std::endl;
        }
    }

    infile.close();

    // Write the filtered content back to the file
    lseek(fd, 0, SEEK_SET);
    ftruncate(fd, 0);
    std::string tempString = tempContent.str();
    write(fd, tempString.c_str(), tempString.size());

    flock(fd, LOCK_UN);
    close(fd);
}
