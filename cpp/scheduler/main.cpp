#include <iostream>
#include "ConfigManager.h"
#include "FileRequestSource.h"
#include "Scheduler.h"
#include "UtilityFunctions.h"

int main() {
    const std::string configFilePath = "/home/user/WORK/config/config.ini";
    const std::string requestsFilePath = "/dev/shm/REQUESTS.txt";
    const std::string workUnitStats = "/home/user/WORK/tmp/workUnitStats.txt";

    // Initialize ConfigManager with the config file path
    ConfigManager configManager(configFilePath);

    // Initialize ConfigManager with the workUnitStats file path
    ConfigManager workUnitStatsConfig(workUnitStats);

    // Initialize FileRequestProvider with the requests file path and maximum number of requests
    FileRequestSource fileRequestSource(requestsFilePath);

    // Initialize Scheduler with ConfigManager and FileRequestProvider
    Scheduler scheduler(configManager, workUnitStatsConfig, fileRequestSource);

    // Run the scheduler
    scheduler.run();

    return 0;
}
