#ifndef SCHEDULER_H
#define SCHEDULER_H

#include <vector>
#include <map>
#include <chrono>
#include "ConfigManager.h"
#include "RequestSource.h"
#include "WorkUnit.h"
#include <memory>

class Scheduler
{
public:
	Scheduler(ConfigManager& config, ConfigManager& workUnitStatsConfig, RequestSource& requestSource);

	void run();


private:
	ConfigManager& config;
	ConfigManager& workUnitStatsConfig;
	RequestSource& requestSource;

	std::map<std::string, std::shared_ptr<WorkUnit>> workStats;
	std::map<std::string, std::shared_ptr<WorkUnit>> runningProcesses;

	void loadWorkUnits();
	void runScheduler();
	void processCompletedRequests(std::vector<Request>& requests);
	void processNormalRequests(std::vector<Request>& requests);

	void handleCompletedRequest(const Request& request);
	void runProcess(const Request& request);

	bool isEvaluationRequired(const Request& request);

	bool processRequest(const Request& request);
	void performProcessLoadDiscovery(const Request& request);
	float getCpuTempEstimate();
	bool canRunProcess(const Request& request);

	void coolOff();
	bool waitForProcessToComplete(const Request& request, const int waitInterval, const bool failFast);
	void waitForAllProcessesToComplete();
	bool hasProcessCompleted(const Request& request, const std::vector<Request>& requests);

	bool isCpuTempCritical();
	void sleep(const int seconds);
	void sleepForInterval();
};

#endif // SCHEDULER_H
