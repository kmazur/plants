#include "FileRequestProvider.h"
#include "UtilityFunctions.h"
#include <fstream>
#include <sstream>

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
