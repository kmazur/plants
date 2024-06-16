#include "TokenManager.h"
#include "UtilityFunctions.h"
#include <cmath>
#include <ctime>

TokenManager::TokenManager(const ConfigManager& config) : config(config) {
    lastReplenishTime = std::chrono::steady_clock::now();
    availableTokens = config.getInitialTokens();
}

void TokenManager::adjustReplenishRate() {
    this->cpuTemp = getCpuTempInt();
    this->cpuTempEstimate = this->cpuTemp;
    double temp = this->cpuTemp;
    double minTemp = config.getMinTemp();
    double maxTemp = config.getMaxTemp();
    double baseReplenishRate = config.getReplenishRate();

    if (temp < minTemp) {
        replenishRate = baseReplenishRate;
    } else if (temp >= maxTemp) {
        replenishRate = 0.0;
    } else {
        replenishRate = baseReplenishRate - ((temp - minTemp) / (maxTemp - minTemp) * baseReplenishRate);
    }
}

void TokenManager::replenishTokens() {
    auto now = std::chrono::steady_clock::now();
    double elapsedTime = std::chrono::duration<double>(now - lastReplenishTime).count();
    double tokensToAdd = elapsedTime * replenishRate;

    double totalAccumulatedTokens = 0;
    for (const auto& pair : accumulatedTokens) {
        totalAccumulatedTokens += pair.second;
    }

    double maxTokens = config.getMaxTokens();
    double availableCapacity = maxTokens - totalAccumulatedTokens;
    if (tokensToAdd + availableTokens > availableCapacity) {
        tokensToAdd = availableCapacity - availableTokens;
    }

    if (tokensToAdd > 0) {
        availableTokens += tokensToAdd;
    }

    lastReplenishTime = now;
}

bool TokenManager::canFulfillRequest(const std::string& process, double requestedTokens) {
    double maxTemp = config.getMaxTemp();
    return cpuTempEstimate + requestedTokens <= maxTemp;
}

void TokenManager::fulfillRequest(const std::string& process, double requestedTokens) {
    this->cpuTempEstimate += requestedTokens;
}

void TokenManager::accumulateTokens(const std::string& process, double tokensToAccumulate) {
}

double TokenManager::getAvailableTokens() const {
    double maxTemp = config.getMaxTemp();
    return maxTemp - cpuTempEstimate;
}

double TokenManager::getAccumulatedTokens(const std::string& process) const {
    return 0.0;
}
