#include <iostream>
#include "ConfigManager.h"
#include "FileRequestProvider.h"
#include "Scheduler.h"
#include "UtilityFunctions.h"

int main() {
    const std::string configFilePath = "/home/user/WORK/config/config.ini";
    const std::string requestsFilePath = "/dev/shm/REQUESTS.txt";
    const size_t maxRequests = 100;

    // Initialize ConfigManager with the config file path
    ConfigManager configManager(configFilePath);

    // Initialize FileRequestProvider with the requests file path and maximum number of requests
    FileRequestProvider fileRequestProvider(requestsFilePath, maxRequests);

    // Initialize Scheduler with ConfigManager and FileRequestProvider
    Scheduler scheduler(configManager, fileRequestProvider);

    // Run the scheduler
    scheduler.run();

    return 0;
}
