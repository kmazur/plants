#ifndef UTILITYFUNCTIONS_H
#define UTILITYFUNCTIONS_H

#include <string>

void log(const std::string& message);
void wakeUpProcess(pid_t pid);
void ensureFileExists(const std::string& filePath);
int getCpuTempInt();
time_t dateCompactToEpoch(const std::string& inputDate);

#endif // UTILITYFUNCTIONS_H
