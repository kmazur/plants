#ifndef TOKENMANAGER_H
#define TOKENMANAGER_H

#include <chrono>
#include <map>
#include <string>
#include "ConfigManager.h"  // Assume ConfigManager is defined in this file

class TokenManager {
public:
    TokenManager(const ConfigManager& config);

    void adjustReplenishRate();
    void replenishTokens();
    bool canFulfillRequest(const std::string& process, double requestedTokens);
    void fulfillRequest(const std::string& process, double requestedTokens);
    void accumulateTokens(const std::string& process, double tokensToAccumulate);
    double getAvailableTokens() const;
    double getAccumulatedTokens(const std::string& process) const;

private:
    double availableTokens;
    double replenishRate;
    double cpuTemp;
    double cpuTempEstimate;
    std::chrono::steady_clock::time_point lastReplenishTime;
    std::map<std::string, double> accumulatedTokens;
    const ConfigManager& config;
};

#endif // TOKENMANAGER_H
