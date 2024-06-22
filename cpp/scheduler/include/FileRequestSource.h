#ifndef FILEREQUESTSOURCE_H
#define FILEREQUESTSOURCE_H

#include <vector>
#include <string>
#include "RequestSource.h"

class FileRequestSource : public RequestSource
{
public:
	FileRequestSource(const std::string& filePath);

	const std::vector<Request>& getRequests() const override;
	void markRequestFulfilled(const Request& request) override;
	void markRequestFulfilled(const std::string& request) override;

private:
	std::string filePath;
	mutable std::vector<Request> requests;

	void parseLine(const std::string& line, Request& request) const;
	void removeRequestLine(const std::string& process);
};

#endif // FILEREQUESTSOURCE_H