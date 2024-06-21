#ifndef CONFIGMANAGER_H
#define CONFIGMANAGER_H

#include <string>
#include <map>

class ConfigManager
{
public:
    ConfigManager(const std::string &configFilePath);

    void loadConfig();
    void setConfig(const std::string &key, const std::string &value);
    std::string getOrSetConfig(const std::string &key, const std::string &defaultValue);

    float getMaxTemp() const;
    float getRunInterval() const;
    float getProcessReevaluationInterval() const;
    float getCoolOffTime() const;
    float getRequiredEvaluationCount() const;

private:
    std::string configFilePath;
    std::map<std::string, std::string> configValues;

    void readConfigFile();
    void writeConfigFile();

    float maxTemp;
    float runInterval;
    float reevaluationInterval;
    float coolOffTime;
    float requiredEvaluationCount;
};

#endif // CONFIGMANAGER_H
