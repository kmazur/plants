#include "Scheduler.h"
#include "UtilityFunctions.h"
#include <algorithm>
#include <thread>
#include <iostream>

Scheduler::Scheduler(const ConfigManager& config, RequestProvider& requestProvider)
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
            ", Replenish rate: " + std::to_string(tokenManager.getReplenishRate()));

        std::this_thread::sleep_for(std::chrono::seconds(static_cast<int>(config.getRunInterval())));
    }
}

void Scheduler::runScheduler() {
    const std::vector<Request>& requests = requestProvider.getRequests();

    std::sort(requests.begin(), requests.end(), [](const Request& a, const Request& b) {
        return a.waitTime > b.waitTime;
    });

    for (const auto& request : requests) {
        if (tokenManager.canFulfillRequest(request.process, request.requestedTokens)) {
            tokenManager.fulfillRequest(request.process, request.requestedTokens);
            wakeUpProcess(request.sleepPid);
            requestProvider.markRequestFulfilled(request.process);
        } else {
            if (request.waitTime > config.getReserveThreshold()) {
                tokenManager.accumulateTokens(request.process, tokenManager.getAvailableTokens(), requests.size());
            }
        }
    }
}
