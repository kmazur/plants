#pragma once

#include <string>
#include <ctime>
#include <deque>
#include <memory>
#include <numeric>
#include <algorithm>
#include <sstream>

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
		lastGroupId(0),
		cpuTempIncreasePerToken(0.0f),
		secondsPerToken(1.0f),
		startTime(0),
		lastRequestedTokens(0) {
	}

	std::string name;
	time_t lastEvaluationEpoch;
	pid_t lastGroupId;

	time_t startTime;
	int lastRequestedTokens;

	float cpuTempIncreasePerToken;
	float secondsPerToken;

	void addEvaluation(int requestedTokens, int durationSeconds, float cpuTempIncrease, pid_t pgid) {
		if (evaluations.size() == 10) {
			evaluations.pop_front();
		}
		evaluations.emplace_back(std::make_shared<Evaluation>(requestedTokens, durationSeconds, cpuTempIncrease));
		lastEvaluationEpoch = std::time(nullptr);
		lastGroupId = pgid;
		calculate();
	}

	int getEvaluationCount() const {
		return this->evaluations.size();
	}


	std::string serialize() const {
		std::ostringstream oss;
		oss << name << ";"
			<< lastEvaluationEpoch << ";"
			<< lastGroupId << ";"
			<< startTime << ";"
			<< lastRequestedTokens << ";"
			<< cpuTempIncreasePerToken << ";"
			<< secondsPerToken << ";";

		for (const auto& ev : evaluations) {
			oss << ev->requestedTokens << ","
				<< ev->durationSeconds << ","
				<< ev->cpuTempIncrease << "|";
		}

		return oss.str();
	}

	static int getCharCount(const std::string& data, const char c) {
		std::istringstream iss(data);

		char ch;
		int count = 0;

		while (iss.get(ch)) {
			if (ch == c) {
				++count;
			}
		}
		return c;
	}


	static WorkUnit deserialize(const std::string& data) {
		std::istringstream iss(data);
		std::string token;

		std::getline(iss, token, ';');
		WorkUnit wu(token);

		std::getline(iss, token, ';');
		wu.lastEvaluationEpoch = std::stol(token);

		if (getCharCount(data, ';') == 7) {
			std::getline(iss, token, ';');
			wu.lastGroupId = std::stoi(token);
		}

		std::getline(iss, token, ';');
		wu.startTime = std::stol(token);

		std::getline(iss, token, ';');
		wu.lastRequestedTokens = std::stoi(token);

		std::getline(iss, token, ';');
		wu.cpuTempIncreasePerToken = std::stof(token);

		std::getline(iss, token, ';');
		wu.secondsPerToken = std::stof(token);

		std::getline(iss, token, ';');
		std::istringstream evStream(token);
		std::string evToken;
		while (std::getline(evStream, evToken, '|')) {
			std::istringstream evFields(evToken);
			std::string evField;
			std::getline(evFields, evField, ',');
			int requestedTokens = std::stoi(evField);
			std::getline(evFields, evField, ',');
			int durationSeconds = std::stoi(evField);
			std::getline(evFields, evField, ',');
			float cpuTempIncrease = std::stof(evField);

			wu.evaluations.emplace_back(std::make_shared<Evaluation>(requestedTokens, durationSeconds, cpuTempIncrease));
		}

		return wu;
	}

private:

	std::deque<std::shared_ptr<Evaluation>> evaluations;

	void calculate() {
		int totalTokensRequested = 0;
		float totalCpuIncreased = 0;
		float totalDuration = 0;
		for (const auto& ev : evaluations) {
			totalTokensRequested += ev->requestedTokens;
			totalCpuIncreased += ev->cpuTempIncrease;
			totalDuration += ev->durationSeconds;
		}
		this->cpuTempIncreasePerToken = static_cast<float>(totalCpuIncreased) / totalTokensRequested;
		this->secondsPerToken = static_cast<float>(totalDuration) / totalTokensRequested;
	}

};