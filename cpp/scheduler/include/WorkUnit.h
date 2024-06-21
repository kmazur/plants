#pragma once

#include <string>
#include <ctime>
#include <vector>
#include <memory>
#include <numeric>
#include <algorithm>

struct Evaluation {
	int requestedTokens;
	int durationSeconds;
	float cpuTempIncrease;
	Evaluation(int requestedTokens, int durationSeconds, float cpuTempIncrease)
		: requestedTokens(requestedTokens), durationSeconds(durationSeconds), cpuTempIncrease(cpuTempIncrease) {}
};

class WorkUnit {
public:

	WorkUnit(const std::string& name) :
		name(name),
		lastEvaluationEpoch(0),
		cpuTempIncreasePerToken(0.0f),
		secondsPerToken(1.0f),
		startTime(0),
		lastRequestedTokens(0) {
	}

	std::string name;
	time_t lastEvaluationEpoch;

	time_t startTime;
	int lastRequestedTokens;

	float cpuTempIncreasePerToken;
	float secondsPerToken;

	void addEvaluation(int requestedTokens, int durationSeconds, float cpuTempIncrease) {
		evaluations.emplace_back(std::make_shared<Evaluation>(requestedTokens, durationSeconds, cpuTempIncrease));
		calculate();
		lastEvaluationEpoch = std::time(nullptr);
	}

	int getEvaluationCount() const {
		return this->evaluations.size();
	}

private:

	std::vector<std::shared_ptr<Evaluation>> evaluations;

	void calculate() {
		int totalTokensRequested = 0;
		int totalCpuIncreased = 0;
		int totalDuration = 0;
		for (const auto& ev : evaluations) {
			totalTokensRequested += ev->requestedTokens;
			totalCpuIncreased += ev->cpuTempIncrease;
			totalDuration += ev->cpuTempIncrease;
		}
		this->cpuTempIncreasePerToken = static_cast<float>(totalCpuIncreased) / totalTokensRequested;
		this->secondsPerToken = static_cast<float>(totalDuration) / totalTokensRequested;
	}

};