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

std::ostream& formatDouble(std::ostream& os) {
    return os << std::fixed << std::setw(8) << std::setprecision(4);
}

Scheduler::Scheduler(ConfigManager& config, RequestProvider& requestProvider)
    : config(config), tokenManager(config), requestProvider(requestProvider) {
    ensureFileExists(ORCHESTRATOR_REQUESTS_FILE);
}

void Scheduler::run() {
    while (true) {
        config.loadConfig();

        tokenManager.adjustReplenishRate();
        tokenManager.replenishTokens();

        log("Available tokens: " + std::to_string(tokenManager.getAvailableTokens()) + ", cpu temperature: " + std::to_string(getCpuTempInt()));
        runScheduler();
        log("Available tokens: " + std::to_string(tokenManager.getAvailableTokens()) + ", cpu temperature: " + std::to_string(getCpuTempInt()));

        std::this_thread::sleep_for(std::chrono::seconds(static_cast<int>(config.getRunInterval())));
    }
}

void Scheduler::runScheduler() {
    const std::vector<Request>& requests = requestProvider.getRequests();

    size_t numProcesses = requests.size();
    std::vector<std::pair<std::string, std::string>> runPass;

    int maxRun = 4;
    int maxRunCount = 0;
    for (size_t i = 0; i < requests.size(); ++i) {
        const auto& request = requests[i];
        std::string process = request.process;
        double tokens = request.requestedTokens;
        double waitTime = request.waitTime;
        double estimatedTokens = tokens;

        std::ostringstream logStream;

        if (tokenManager.canFulfillRequest(request.process, request.requestedTokens) && maxRunCount < maxRun) {
            logStream << "RUN        (r: "
                      << formatDouble << request.requestedTokens << "/"
                      << formatDouble << tokenManager.getAccumulatedTokens(request.process)
                      << ", a: "
                      << formatDouble << tokenManager.getAvailableTokens()
                      << " - "
                      << formatDouble << (request.requestedTokens - tokenManager.getAccumulatedTokens(request.process))
                      << ", w: "
                      << formatDouble << request.waitTime << ")";
            tokenManager.fulfillRequest(request.process, request.requestedTokens);
            wakeUpProcess(request.sleepPid);
            requestProvider.markRequestFulfilled(request.process);
            ++maxRunCount;
        } else {
             logStream << "SKIP       (r: "
                       << formatDouble << request.requestedTokens << "/"
                       << formatDouble << tokenManager.getAccumulatedTokens(request.process)
                       << ", a: "
                       << formatDouble << tokenManager.getAvailableTokens()
                       << ", w: "
                       << formatDouble << request.waitTime << ")";
        }

        runPass.emplace_back(process, logStream.str());
    }

    for (const auto& entry : runPass) {
        std::cout << std::setw(60) << std::right << entry.first << ": " << entry.second << std::endl;
    }
}
