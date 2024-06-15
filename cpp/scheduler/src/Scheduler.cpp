#include "Scheduler.h"
#include "UtilityFunctions.h"
#include <algorithm>
#include <thread>
#include <iostream>
#include <sstream>
#include <iomanip>
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

    for (const auto& request : requests) {
        std::ostringstream logStream;


        if (tokenManager.canFulfillRequest(request.process, request.requestedTokens)) {
            logStream << "RUN (r: " << request.requestedTokens << "/" << tokenManager.getAccumulatedTokens(request.process)
                                      << ", a: " << tokenManager.getAvailableTokens() << ")";
            tokenManager.fulfillRequest(request.process, request.requestedTokens);
            wakeUpProcess(request.sleepPid);
            requestProvider.markRequestFulfilled(request.process);

        } else {
            if (request.waitTime > config.getReserveThreshold()) {
                tokenManager.accumulateTokens(request.process, tokenManager.getAvailableTokens(), requests.size());
                logStream << "ACCUMULATE (r: " << request.requestedTokens << "/" << tokenManager.getAccumulatedTokens(request.process)
                                          << ", a: " << tokenManager.getAvailableTokens() << ")";
            } else {
                 logStream << "SKIP (r: " << request.requestedTokens << "/" << tokenManager.getAccumulatedTokens(request.process)
                           << ", a: " << tokenManager.getAvailableTokens() << ")";
             }
        }

        runPass[request.process] = logStream.str();
    }

    for (const auto& entry : runPass) {
        std::cout << std::setw(50) << std::left << entry.first << ": " << entry.second << std::endl;
    }
}
