#ifndef UTILITYFUNCTIONS_H
#define UTILITYFUNCTIONS_H

#include "Request.h"
#include <string>
#include <ctime>
#include <vector>
#include <map>
#include <unistd.h>

void log(const std::string &message);
void wakeUpProcess(const Request& request);
void wakeUpProcess(const int pid);
void killGroup(const int pgid);
void ensureFileExists(const std::string &filePath);
int getCpuTempInt();
float getCpuTempFloat();
time_t dateCompactToEpoch(const std::string &inputDate);
std::string vectorToString(const std::vector<std::string>& vec);

template <typename T>
std::vector<std::string> getKeys(const std::map<std::string, T>& map) {
    std::vector<std::string> keys;
    keys.reserve(map.size());

    for (const auto& entry : map) {
        keys.push_back(entry.first);
    }
    return keys;
}

#endif // UTILITYFUNCTIONS_H
