#include "Scheduler.h"
#include "UtilityFunctions.h"
#include <algorithm>
#include <thread>
#include <iostream>
#include <sstream>
#include <iomanip>
#include <cmath>
#include "ConfigManager.h"

const std::string ORCHESTRATOR_REQUESTS_FILE = "/dev/shm/REQUESTS.txt";

Scheduler::Scheduler(ConfigManager& config, RequestProvider& requestProvider)
    : config(config), tokenManager(config), requestProvider(requestProvider) {
    ensureFileExists(ORCHESTRATOR_REQUESTS_FILE);
}

void Scheduler::run() {
    while (true) {
        config.loadConfig();

        double currentTemp = getCpuTempInt();
        tokenManager.adjustReplenishRate(currentTemp);
        tokenManager.replenishTokens();
        runScheduler();

        log("Available tokens: " + std::to_string(tokenManager.getAvailableTokens()) +
            ", Replenish rate: " + std::to_string(config.getReplenishRate()));

        std::this_thread::sleep_for(std::chrono::seconds(static_cast<int>(config.getRunInterval())));
    }
}

void Scheduler::runScheduler() {
    const std::vector<Request>& requests = requestProvider.getRequests();

    size_t numProcesses = requests.size();
    std::map<std::string, std::string> runPass;

    // Calculate total weight for the first 4 processes with waitTime > reserveThreshold
    double totalWeight = 0.0;
    size_t count = 0;
    for (size_t i = 0; i < numProcesses && count < 4; ++i) {
        if (requests[i].waitTime > config.getReserveThreshold()) {
            totalWeight += (numProcesses - i);
            ++count;
        }
    }

    count = 0;
    for (size_t i = 0; i < requests.size(); ++i) {
        const auto& request = requests[i];
        std::string process = request.process;
        double tokens = request.requestedTokens;
        double waitTime = request.waitTime;
        double estimatedTokens = tokens;

        std::ostringstream logStream;

        if (tokenManager.canFulfillRequest(request.process, request.requestedTokens)) {
            logStream << "RUN        (r: " << request.requestedTokens << "/" << tokenManager.getAccumulatedTokens(request.process)
                                      << ", a: " << tokenManager.getAvailableTokens()
                                      << ", w: " << request.waitTime << ")";
            tokenManager.fulfillRequest(request.process, request.requestedTokens);
            wakeUpProcess(request.sleepPid);
            requestProvider.markRequestFulfilled(request.process);
        } else {
            if (request.waitTime > config.getReserveThreshold() && count < 4) {
                double positionWeight = (numProcesses - i);
                double accumulationFactor = 0.1 + (0.9 * (tokenManager.getAvailableTokens() / config.getMaxTokens()));
                double tokensToAccumulate = (tokenManager.getAvailableTokens() * accumulationFactor * positionWeight) / totalWeight;
                tokenManager.accumulateTokens(process, tokensToAccumulate);
                logStream << "ACCUMULATE (r: " << request.requestedTokens << "/" << tokenManager.getAccumulatedTokens(request.process)
                                          << ", a: " << tokenManager.getAvailableTokens()
                                          << ", w: " << request.waitTime << ")";
            } else {
                 logStream << "SKIP       (r: " << request.requestedTokens << "/" << tokenManager.getAccumulatedTokens(request.process)
                           << ", a: " << tokenManager.getAvailableTokens()
                           << ", w: " << request.waitTime << ")";
             }
        }

        runPass[request.process] = logStream.str();
    }

    for (const auto& entry : runPass) {
        std::cout << std::setw(50) << std::left << entry.first << ": " << entry.second << std::endl;
    }
}
