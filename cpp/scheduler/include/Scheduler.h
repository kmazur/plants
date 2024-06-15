#ifndef SCHEDULER_H
#define SCHEDULER_H

#include <vector>
#include "ConfigManager.h"  // Assume ConfigManager is defined in this file
#include "TokenManager.h"
#include "RequestProvider.h"

class Scheduler {
public:
    Scheduler(const ConfigManager& config, RequestProvider& requestProvider);

    void run();

private:
    ConfigManager& config;
    TokenManager tokenManager;
    RequestProvider& requestProvider;

    void runScheduler();
};

#endif // SCHEDULER_H
