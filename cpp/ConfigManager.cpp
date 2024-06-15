#include "ConfigManager.h"
#include "UtilityFunctions.h"
#include <fstream>
#include <sstream>
#include <sys/file.h>
#include <unistd.h>
#include <iostream>

ConfigManager::ConfigManager(const std::string& configFilePath)
    : configFilePath(configFilePath) {
    loadConfig();
}

void ConfigManager::loadConfig() {
    readConfigFile();
    maxTemp = std::stod(getOrSetConfig("orchestrator.max_temperature", "79"));
    minTemp = std::stod(getOrSetConfig("orchestrator.min_temperature", "50"));
    initialTokens = std::stod(getOrSetConfig("orchestrator.initial_tokens", "0"));
    maxTokens = std::stod(getOrSetConfig("orchestrator.max_tokens", "100"));
    replenishRate = std::stod(getOrSetConfig("orchestrator.replenish_rate", "10"));
    reserveThreshold = std::stod(getOrSetConfig("orchestrator.accumulation_threshold_seconds", "60"));
    runInterval = std::stod(getOrSetConfig("orchestrator.run_interval", "5"));
}

std::string ConfigManager::getOrSetConfig(const std::string& key, const std::string& defaultValue) {
    if (configValues.find(key) == configValues.end()) {
        setConfig(key, defaultValue);
    }
    return configValues[key];
}

void ConfigManager::setConfig(const std::string& key, const std::string& value) {
    configValues[key] = value;
    writeConfigFile();
}

void ConfigManager::readConfigFile() {
    int fd = open(configFilePath.c_str(), O_RDONLY);
    if (fd == -1) {
        return; // Error handling, could not open the file
    }

    if (flock(fd, LOCK_SH) == -1) {
        close(fd);
        return; // Error handling, could not lock the file
    }

    std::ifstream infile(configFilePath);
    std::string line;
    while (std::getline(infile, line)) {
        std::istringstream ss(line);
        std::string key, value;
        if (std::getline(ss, key, '=') && std::getline(ss, value)) {
            configValues[key] = value;
        }
    }

    flock(fd, LOCK_UN);
    close(fd);
}

void ConfigManager::writeConfigFile() {
    int fd = open(configFilePath.c_str(), O_WRONLY);
    if (fd == -1) {
        return; // Error handling, could not open the file
    }

    if (flock(fd, LOCK_EX) == -1) {
        close(fd);
        return; // Error handling, could not lock the file
    }

    std::ofstream outfile(configFilePath);
    for (const auto& pair : configValues) {
        outfile << pair.first << "=" << pair.second << std::endl;
    }

    flock(fd, LOCK_UN);
    close(fd);
}

double ConfigManager::getMaxTemp() const { return maxTemp; }
double ConfigManager::getMinTemp() const { return minTemp; }
double ConfigManager::getInitialTokens() const { return initialTokens; }
double ConfigManager::getMaxTokens() const { return maxTokens; }
double ConfigManager::getReplenishRate() const { return replenishRate; }
double ConfigManager::getReserveThreshold() const { return reserveThreshold; }
double ConfigManager::getRunInterval() const { return runInterval; }
