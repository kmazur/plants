#include <iostream>
#include <fcntl.h>
#include <unistd.h>
#include <cstring>
#include <fstream>
#include <vector>
#include <string>
#include <map>
#include <regex>
#include <algorithm>
#include <chrono>
#include <thread>
#include <cmath>
#include <csignal>

int getCpuTempInt() {
    const char* path = "/sys/class/thermal/thermal_zone0/temp";
    int fd = open(path, O_RDONLY);
    char buffer[2];
    ssize_t bytesRead = pread(fd, buffer, 2, 0);
    close(fd);
    int temp = (buffer[0] - '0') * 10 + (buffer[1] - '0');
    return temp;
}


extern std::string getOrSetConfig(const std::string& key, const std::string& defaultValue);
extern void ensureFileExists(const std::string& filename);
extern double dateCompactToEpoch(const std::string& datetime);
extern double getCpuTempInt();
extern void log(const std::string& message);
extern void wakeUpProcess(pid_t pid);
extern void removeConfig(const std::string& process, const std::string& filename);

const std::string ORCHESTRATOR_REQUESTS_FILE = "/dev/shm/REQUESTS.txt";


class ConfigManager {
public:
    void loadConfig() {
        maxTemp = std::stod(getOrSetConfig("orchestrator.max_temperature", "79"));
        minTemp = std::stod(getOrSetConfig("orchestrator.min_temperature", "50"));
        initialTokens = std::stod(getOrSetConfig("orchestrator.initial_tokens", "0"));
        maxTokens = std::stod(getOrSetConfig("orchestrator.max_tokens", "100"));
        replenishRate = std::stod(getOrSetConfig("orchestrator.replenish_rate", "10"));
        reserveThreshold = std::stod(getOrSetConfig("orchestrator.accumulation_threshold_seconds", "60"));
        runInterval = std::stod(getOrSetConfig("orchestrator.run_interval", "5"));
    }

    double getMaxTemp() const { return maxTemp; }
    double getMinTemp() const { return minTemp; }
    double getInitialTokens() const { return initialTokens; }
    double getMaxTokens() const { return maxTokens; }
    double getReplenishRate() const { return replenishRate; }
    double getReserveThreshold() const { return reserveThreshold; }
    double getRunInterval() const { return runInterval; }

private:
    double maxTemp;
    double minTemp;
    double initialTokens;
    double maxTokens;
    double replenishRate;
    double reserveThreshold;
    double runInterval;
};

struct Request {
    std::string process;
    double requestedTokens;
    double requestTimestamp;
    pid_t sleepPid;
    double waitTime;
};

class RequestParser {
public:
    std::vector<Request> parseRequests(const std::string& filePath) {
        std::vector<Request> requests;
        std::ifstream infile(filePath);
        std::string line;

        while (std::getline(infile, line)) {
            std::istringstream ss(line);
            std::string process, tokensStr, pidStr, datetime;

            std::getline(ss, process, '=');
            std::getline(ss, tokensStr, ':');
            std::getline(ss, pidStr, ':');
            std::getline(ss, datetime);

            Request request;
            request.process = process;
            request.requestedTokens = std::stod(tokensStr);
            request.sleepPid = std::stoi(pidStr);
            request.requestTimestamp = dateCompactToEpoch(datetime);
            request.waitTime = std::time(nullptr) - request.requestTimestamp;

            requests.push_back(request);
        }

        return requests;
    }
};

class TokenManager {
public:
    TokenManager(const ConfigManager& config) : config(config) {
        lastReplenishTime = std::chrono::steady_clock::now();
        availableTokens = config.getInitialTokens();
    }

    void adjustReplenishRate(double temp) {
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

    void replenishTokens() {
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

    bool canFulfillRequest(const std::string& process, double requestedTokens) {
        return availableTokens + accumulatedTokens[process] >= requestedTokens;
    }

    void fulfillRequest(const std::string& process, double requestedTokens) {
        availableTokens -= (requestedTokens - accumulatedTokens[process]);
        accumulatedTokens.erase(process);
    }

    void accumulateTokens(const std::string& process, double availableTokens, int numProcesses) {
        double maxTokens = config.getMaxTokens();
        double accumulationFactor = 0.1 + (0.9 * (availableTokens / maxTokens));
        double tokensToAccumulate = availableTokens * accumulationFactor / numProcesses;
        accumulatedTokens[process] += tokensToAccumulate;
        this->availableTokens -= tokensToAccumulate;
    }

    double getAvailableTokens() const {
        return availableTokens;
    }

private:
    double availableTokens;
    double replenishRate;
    std::chrono::steady_clock::time_point lastReplenishTime;
    std::map<std::string, double> accumulatedTokens;
    const ConfigManager& config;
};

class Scheduler {
public:
    Scheduler(const ConfigManager& config) : config(config), tokenManager(config), requestParser() {
        ensureFileExists(ORCHESTRATOR_REQUESTS_FILE);
    }

    void run() {
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

private:
    void runScheduler() {
        std::vector<Request> requests = requestParser.parseRequests(ORCHESTRATOR_REQUESTS_FILE);

        std::sort(requests.begin(), requests.end(), [](const Request& a, const Request& b) {
            return a.waitTime > b.waitTime;
        });

        for (const auto& request : requests) {
            if (tokenManager.canFulfillRequest(request.process, request.requestedTokens)) {
                tokenManager.fulfillRequest(request.process, request.requestedTokens);
                wakeUpProcess(request.sleepPid);
                removeConfig(request.process, ORCHESTRATOR_REQUESTS_FILE);
            } else {
                if (request.waitTime > config.getReserveThreshold()) {
                    tokenManager.accumulateTokens(request.process, tokenManager.getAvailableTokens(), requests.size());
                }
            }
        }
    }

    const ConfigManager& config;
    TokenManager tokenManager;
    RequestParser requestParser;
};

int main() {
    ConfigManager config;
    config.loadConfig();
    Scheduler scheduler(config);
    scheduler.run();

    return 0;
}