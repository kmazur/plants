#ifndef REQUEST_H
#define REQUEST_H

#include <string>
#include <sys/types.h>
#include <unistd.h>

struct Request
{
	std::string process;
	double requestedTokens;
	double requestTimestamp;
	pid_t sleepPid;
	double waitTime;

	bool isCompleted() const {
		const int len = process.size();
		return len >= 10 && process.rfind("-completed") == (len - 10);
	}

	std::string getName() const {
		if (this->isCompleted()) {
			return process.substr(0, process.find("-completed"));
		}
		return process;
	}
};

#endif // REQUEST_H
