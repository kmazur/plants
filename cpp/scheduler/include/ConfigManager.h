#ifndef CONFIGMANAGER_H
#define CONFIGMANAGER_H

#include <string>
#include <map>
#include <iostream>
#include "WorkUnit.h"

class ConfigManager
{
public:
    ConfigManager(const std::string &configFilePath);

    void loadConfig();
    void setConfig(const std::string &key, const std::string &value);
    std::string getOrSetConfig(const std::string &key, const std::string &defaultValue);

    float getMinTemp() const;
    float getMaxTemp() const;
    float getRunInterval() const;
    float getProcessReevaluationInterval() const;
    float getCoolOffTime() const;
    float getRequiredEvaluationCount() const;

    void saveWorkUnit(const WorkUnit& workUnit);
    WorkUnit loadWorkUnit(const std::string& name);
    std::vector<WorkUnit> loadAllWorkUnits();

private:
    std::string configFilePath;
    std::map<std::string, std::string> configValues;

    void readConfigFile();
    void writeConfigFile();

    float minTemp;
    float maxTemp;
    float runInterval;
    float reevaluationInterval;
    float coolOffTime;
    float requiredEvaluationCount;
};

#endif // CONFIGMANAGER_H
