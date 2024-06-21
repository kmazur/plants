#include "FileRequestSource.h"
#include "UtilityFunctions.h"
#include "ConfigManager.h"
#include <fstream>
#include <sstream>
#include <algorithm>
#include <sys/file.h>
#include <ctime>

FileRequestSource::FileRequestSource(const std::string& filePath)
	: filePath(filePath) {}

const std::vector<Request>& FileRequestSource::getRequests() const
{
	requests.clear();
	std::ifstream infile(filePath);
	if (!infile.is_open())
	{
		// Error handling
		return requests;
	}
	std::string line;

	while (std::getline(infile, line))
	{
		if (line.empty())
		{
			continue;
		}
		Request request;
		parseLine(line, request);
		requests.push_back(request);
	}

	std::sort(requests.begin(), requests.end(), [](const Request& a, const Request& b)
		{ return a.waitTime > b.waitTime; });

	return requests;
}

void FileRequestSource::parseLine(const std::string& line, Request& request) const
{
	std::istringstream ss(line);
	std::string process, tokensStr, pidStr, datetime;

	std::getline(ss, process, '=');
	std::getline(ss, tokensStr, ':');
	std::getline(ss, pidStr, ':');
	std::getline(ss, datetime);

	request.process = process;
	request.requestedTokens = std::stod(tokensStr);
	request.sleepPid = std::stoi(pidStr);
	request.requestTimestamp = dateCompactToEpoch(datetime);
	request.waitTime = std::time(nullptr) - request.requestTimestamp;
}

void FileRequestSource::markRequestFulfilled(const Request& request)
{
	removeRequestLine(request.process);
}

void FileRequestSource::removeRequestLine(const std::string& process)
{
	int fd = open(filePath.c_str(), O_RDWR);
	if (fd == -1)
	{
		return;
	}

	if (flock(fd, LOCK_EX) == -1)
	{
		close(fd);
		return;
	}

	std::ostringstream tempContent;
	std::ifstream infile(filePath);
	if (!infile.is_open())
	{
		flock(fd, LOCK_UN);
		close(fd);
		return;
	}
	std::string line;

	while (std::getline(infile, line))
	{
		if (line.substr(0, line.find('=')) != process)
		{
			tempContent << line << std::endl;
		}
	}

	infile.close();

	// Write the filtered content back to the file
	lseek(fd, 0, SEEK_SET);
	ftruncate(fd, 0);
	std::string tempString = tempContent.str();
	write(fd, tempString.c_str(), tempString.size());

	flock(fd, LOCK_UN);
	close(fd);
}
