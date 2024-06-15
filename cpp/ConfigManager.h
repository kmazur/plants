#ifndef CONFIGMANAGER_H
#define CONFIGMANAGER_H

#include <string>
#include <map>

class ConfigManager {
public:
    ConfigManager(const std::string& configFilePath);

    void loadConfig();
    void setConfig(const std::string& key, const std::string& value);
    std::string getOrSetConfig(const std::string& key, const std::string& defaultValue);

    double getMaxTemp() const;
    double getMinTemp() const;
    double getInitialTokens() const;
    double getMaxTokens() const;
    double getReplenishRate() const;
    double getReserveThreshold() const;
    double getRunInterval() const;

private:
    std::string configFilePath;
    std::map<std::string, std::string> configValues;

    void readConfigFile();
    void writeConfigFile();
};

#endif // CONFIGMANAGER_H
