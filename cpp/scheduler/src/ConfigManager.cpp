#include "ConfigManager.h"
#include "UtilityFunctions.h"
#include <fstream>
#include <sstream>
#include <sys/file.h>
#include <unistd.h>
#include <iostream>

ConfigManager::ConfigManager(const std::string& configFilePath)
	: configFilePath(configFilePath)
{
	loadConfig();
}

void ConfigManager::loadConfig()
{
	readConfigFile();
	maxTemp = std::stof(getOrSetConfig("orchestrator.max_temperature", "79"));
	runInterval = std::stof(getOrSetConfig("orchestrator.run_interval", "5"));
	reevaluationInterval = std::stof(getOrSetConfig("orchestrator.reevaluation_interval", "7200"));
	coolOffTime = std::stof(getOrSetConfig("orchestrator.cool_off_seconds", "60"));
	requiredEvaluationCount = std::stof(getOrSetConfig("orchestrator.required_evaluation_count", "4"));
}

std::string ConfigManager::getOrSetConfig(const std::string& key, const std::string& defaultValue)
{
	if (configValues.find(key) == configValues.end())
	{
		setConfig(key, defaultValue);
	}
	return configValues[key];
}

void ConfigManager::setConfig(const std::string& key, const std::string& value)
{
	configValues[key] = value;
	writeConfigFile();
}

void ConfigManager::readConfigFile()
{
	int fd = open(configFilePath.c_str(), O_RDONLY);
	if (fd == -1)
	{
		return;
	}

	if (flock(fd, LOCK_SH) == -1)
	{
		close(fd);
		return;
	}

	std::ifstream infile(configFilePath);
	std::string line;
	while (std::getline(infile, line))
	{
		std::istringstream ss(line);
		std::string key, value;
		if (std::getline(ss, key, '=') && std::getline(ss, value))
		{
			configValues[key] = value;
		}
	}

	flock(fd, LOCK_UN);
	close(fd);
}

void ConfigManager::writeConfigFile()
{
	int fd = open(configFilePath.c_str(), O_WRONLY);
	if (fd == -1)
	{
		return; // Error handling, could not open the file
	}

	if (flock(fd, LOCK_EX) == -1)
	{
		close(fd);
		return; // Error handling, could not lock the file
	}

	std::ofstream outfile(configFilePath);
	for (const auto& pair : configValues)
	{
		outfile << pair.first << "=" << pair.second << std::endl;
	}

	flock(fd, LOCK_UN);
	close(fd);
}

float ConfigManager::getMaxTemp() const { return maxTemp; }
float ConfigManager::getRunInterval() const { return runInterval; }
float ConfigManager::getProcessReevaluationInterval() const { return reevaluationInterval; }
float ConfigManager::getCoolOffTime() const { return coolOffTime; }
float ConfigManager::getRequiredEvaluationCount() const { return requiredEvaluationCount; }
