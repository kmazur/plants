#include "TokenManager.h"
#include <cmath>
#include <ctime>

TokenManager::TokenManager(const ConfigManager& config) : config(config) {
    lastReplenishTime = std::chrono::steady_clock::now();
    availableTokens = config.getInitialTokens();
}

void TokenManager::adjustReplenishRate(double temp) {
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
    return availableTokens + accumulatedTokens[process] >= requestedTokens;
}

void TokenManager::fulfillRequest(const std::string& process, double requestedTokens) {
    availableTokens -= (requestedTokens - accumulatedTokens[process]);
    accumulatedTokens.erase(process);
}

void TokenManager::accumulateTokens(const std::string& process, double availableTokens, int numProcesses) {
    double maxTokens = config.getMaxTokens();
    double accumulationFactor = 0.1 + (0.9 * (availableTokens / maxTokens));
    double tokensToAccumulate = availableTokens * accumulationFactor / numProcesses;
    accumulatedTokens[process] += tokensToAccumulate;
    this->availableTokens -= tokensToAccumulate;
}

double TokenManager::getAvailableTokens() const {
    return availableTokens;
}
