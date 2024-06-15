
extern std::string getOrSetConfig(const std::string& key, const std::string& defaultValue);

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
