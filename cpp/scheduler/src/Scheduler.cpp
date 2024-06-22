#include "Scheduler.h"
#include "UtilityFunctions.h"
#include "RequestSource.h"
#include <algorithm>
#include <thread>
#include <iostream>
#include <sstream>
#include <iomanip>
#include <cmath>
#include <fstream>
#include <algorithm>
#include <memory>

const std::string ORCHESTRATOR_REQUESTS_FILE = "/dev/shm/REQUESTS.txt";
const int COOL_OFF_DURATION = 60;

std::ostream& formatDouble(std::ostream& os)
{
	return os << std::fixed << std::setw(8) << std::setprecision(4);
}

Scheduler::Scheduler(ConfigManager& config, ConfigManager& workUnitStatsConfig, RequestSource& requestSource)
	: config(config), workUnitStatsConfig(workUnitStatsConfig), requestSource(requestSource)
{
	ensureFileExists(ORCHESTRATOR_REQUESTS_FILE);
	loadWorkUnits();
}

void Scheduler::run()
{
	while (true)
	{
		log("Scheduler pass started");
		if (!isCpuTempCritical())
		{
			config.loadConfig();
			runScheduler();
		}
		else {
			log("Temperature critical");
			sleep(2 * config.getRunInterval());
		}
		sleepForInterval();
	}
}

void Scheduler::loadWorkUnits() {
	std::vector<WorkUnit> workUnits = workUnitStatsConfig.loadAllWorkUnits();
	for (const auto& workUnit : workUnits) {
		workStats[workUnit.name] = std::make_shared<WorkUnit>(workUnit);
	}
}

void Scheduler::runScheduler()
{
	std::vector<Request> processedRequests = requestSource.getRequests();
	processCompletedRequests(processedRequests);
	processNormalRequests(processedRequests);
}

void Scheduler::processNormalRequests(std::vector<Request>& processedRequests)
{
	for (const auto& request : processedRequests)
	{
		if (!processRequest(request))
		{
			return;
		}
	}
}

void Scheduler::processCompletedRequests(std::vector<Request>& requests)
{
	for (auto it = requests.begin(); it != requests.end();)
	{
		if (it->isCompleted())
		{
			handleCompletedRequest(*it);
			it = requests.erase(it);
		}
		else
		{
			++it;
		}
	}
}

bool Scheduler::isEvaluationRequired(const Request& request) {
	const std::string name = request.getName();
	if (workStats.count(name) == 0) {
		log("Evaluation for process required (0): " + name);
		return true;
	}

	const std::shared_ptr<WorkUnit> unit = workStats[name];
	if (unit->getEvaluationCount() < config.getRequiredEvaluationCount()) {
		log("Evaluation for process required (" + std::to_string(unit->getEvaluationCount()) + "): " + name);
		return true;
	}

	std::time_t now = std::time(nullptr);
	const int reevaluationSeconds = config.getProcessReevaluationInterval();
	bool required = now - unit->lastEvaluationEpoch > reevaluationSeconds;
	if (required) {
		log("Evaluation for process required (timeout " + std::to_string(now - unit->lastEvaluationEpoch) + "s): " + name);
		return true;
	}
	return false;
}

bool Scheduler::processRequest(const Request& request)
{
	if (isEvaluationRequired(request))
	{
		waitForAllProcessesToComplete();
		coolOff();
		performProcessLoadDiscovery(request);
		return false;
	}

	if (canRunProcess(request)) {
		runProcess(request);
		return true;
	}
	return true;
}

bool Scheduler::canRunProcess(const Request& request) {
	float estimatedTemp = getCpuTempEstimate();
	float maxTemp = config.getMaxTemp();

	std::shared_ptr<WorkUnit>& workUnit = workStats[request.process];
	float estimateCpuTempIncrease = workUnit->cpuTempIncreasePerToken * request.requestedTokens;
	return estimatedTemp + estimateCpuTempIncrease <= maxTemp;
}

float Scheduler::getCpuTempEstimate()
{
	float currentTemp = getCpuTempFloat();
	float estimatedTempIncrease = 0.0f;
	std::time_t now = std::time(nullptr);
	for (const auto& entry : runningProcesses)
	{
		std::shared_ptr<WorkUnit> workUnit = entry.second;
		int requestedTokens = workUnit->lastRequestedTokens;

		std::time_t startTime = workUnit->startTime;
		std::time_t elapsed = now - startTime;

		float estimatedTotalDuration = workUnit->secondsPerToken * requestedTokens;
		float stillToGo = std::max(0.0f, estimatedTotalDuration - elapsed);
		float multiplier = stillToGo / estimatedTotalDuration;

		float estimatedTotalCpuTempIncrease = workUnit->cpuTempIncreasePerToken * requestedTokens;
		float stillCpuToIncrease = multiplier * estimatedTotalCpuTempIncrease;
		estimatedTempIncrease += stillCpuToIncrease;
	}
	return currentTemp + estimatedTempIncrease;
}

void Scheduler::handleCompletedRequest(const Request& request)
{
	runningProcesses.erase(request.getName());
	requestSource.markRequestFulfilled(request);
	wakeUpProcess(request);
}

void Scheduler::runProcess(const Request& request)
{
	std::string processName = request.getName();
	if (runningProcesses.count(processName) != 0) {
		log("Trying to run process that has already been running: " + processName);
	}
	log("Running process: " + processName);

	auto& workUnit = workStats[processName];
	runningProcesses[processName] = workUnit;
	workUnit->startTime = std::time(nullptr);
	workUnit->lastRequestedTokens = request.requestedTokens;
	requestSource.markRequestFulfilled(request);
	wakeUpProcess(request);
}

bool Scheduler::hasProcessCompleted(const Request& request, const std::vector<Request>& requests)
{
	const std::string& targetProcess = request.getName();
	for (const auto& r : requests) {
		if (r.getName() == targetProcess && r.isCompleted()) {
			return true;
		}
	}
	return false;
}


bool Scheduler::waitForProcessToComplete(const Request& request, const int waitInterval, const bool failFast) {
	std::time_t startTime = std::time(nullptr);
	const std::string name = request.getName();
	while (true)
	{
		sleep(waitInterval);
		const std::vector<Request>& requests = requestSource.getRequests();
		if (isCpuTempCritical() && failFast) {
			// reached fast the cpu maximum temperature before job was finished!
			return true;
		}

		std::time_t elapsed = std::time(nullptr) - startTime;
		if (hasProcessCompleted(request, requests))
		{
			break;
		}
		else if (elapsed >= config.getProcessRunTimeout()) {
			log("Timed out waiting for " + name + " to complete -> killing");
			if (runningProcesses.count(name) == 0) {
				log("Can't timeout wait because " + name + " is not in the running processes set");
				continue;
			}
			auto& w = runningProcesses[name];
			killGroup(w->lastGroupId);
			requestSource.markRequestFulfilled(w->name);
			requestSource.markRequestFulfilled(w->name + "-completed");
			return false;
		}
		else {
			std::vector<std::string> keys = getKeys(runningProcesses);
			log(name + " has not finished yet, still running: " + vectorToString(keys));
		}
	}
	return false;
}


void Scheduler::performProcessLoadDiscovery(const Request& request)
{
	const std::string name = request.getName();
	pid_t groupId = getpgid(request.sleepPid);

	if (workStats.count(name) == 0) {
		log("Found new work unit: " + name + " performing load evaluation");
		auto unit = std::make_shared<WorkUnit>(name);
		workStats[name] = unit;
	}
	else {
		log("Evaluating load for work unit: " + name);
	}

	auto workUnit = workStats[name];

	float initialTemp = getCpuTempFloat();
	std::time_t startEpoch = std::time(nullptr);
	log(name + " -> initial cpu temp: " + std::to_string(initialTemp));

	runProcess(request);
	bool prematureFinish = waitForProcessToComplete(request, 1, true);

	std::time_t endEpoch = std::time(nullptr);
	float finalTemp = getCpuTempFloat();
	float cpuIncrease = std::max(0.0f, finalTemp - initialTemp);
	int duration = endEpoch - startEpoch;

	if (prematureFinish) {
		log(name + " -> reached critical cpu temp during evaluation: " + std::to_string(finalTemp) + ", increased: " + std::to_string(cpuIncrease) + " elapsed: " + std::to_string(duration));
		waitForProcessToComplete(request, config.getRunInterval(), false);
		endEpoch = std::time(nullptr);
		duration = endEpoch - startEpoch;
		workUnit->addEvaluation(request.requestedTokens, duration, cpuIncrease, groupId);
		log(name + " updated stats: [secondsPerToken: " + std::to_string(workUnit->secondsPerToken) + ", tempPerToken: " + std::to_string(workUnit->cpuTempIncreasePerToken));
	}
	else {
		log(name + " -> completed with cpu temp: " + std::to_string(finalTemp) + ", increased: " + std::to_string(cpuIncrease) + " took: " + std::to_string(duration) + " sec");
		workUnit->addEvaluation(request.requestedTokens, duration, cpuIncrease, groupId);
		log(name + " updated stats: [secondsPerToken: " + std::to_string(workUnit->secondsPerToken) + ", tempPerToken: " + std::to_string(workUnit->cpuTempIncreasePerToken));
	}

	workUnitStatsConfig.saveWorkUnit(*workUnit);
}

void Scheduler::coolOff()
{
	int temp = getCpuTempInt();
	float minTemp = config.getMinTemp();
	if (temp <= config.getMinTemp()) {
		log("No need to cool off - currentTemp(" + std::to_string(temp) + ") < " + std::to_string(minTemp));
	}
	else {
		log("Cooling off for " + std::to_string(config.getCoolOffTime()));
		sleep(config.getCoolOffTime());
	}
}

void Scheduler::waitForAllProcessesToComplete()
{
	log("Wait for all processes to complete");
	std::time_t startTime = std::time(nullptr);
	while (!runningProcesses.empty())
	{
		std::vector<std::string> keys = getKeys(runningProcesses);

		std::time_t elapsed = std::time(nullptr) - startTime;
		if (elapsed >= config.getProcessRunTimeout()) {
			log("Timed out waiting for all processes to complete: " + vectorToString(keys));
			for (auto& w : runningProcesses) {
				killGroup(w.second->lastGroupId);
				requestSource.markRequestFulfilled(w.second->name);
				requestSource.markRequestFulfilled(w.second->name + "-completed");
			}
			break;
		}

		log("Waiting for all processes to complete: " + vectorToString(keys));
		std::vector<Request> copy = requestSource.getRequests();
		processCompletedRequests(copy);
		sleepForInterval();
	}
}

bool Scheduler::isCpuTempCritical()
{
	return getCpuTempInt() >= config.getMaxTemp();
}

void Scheduler::sleep(const int seconds)
{
	std::this_thread::sleep_for(std::chrono::seconds(seconds));
}

void Scheduler::sleepForInterval()
{
	sleep(config.getRunInterval());
}