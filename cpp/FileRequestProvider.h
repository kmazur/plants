#ifndef FILEREQUESTPROVIDER_H
#define FILEREQUESTPROVIDER_H

#include <vector>
#include <string>
#include "RequestProvider.h"

class FileRequestProvider : public RequestProvider {
public:
    FileRequestProvider(const std::string& filePath, size_t maxRequests);

    const std::vector<Request>& getRequests() const override;

private:
    std::string filePath;
    size_t maxRequests;
    mutable std::vector<Request> requests;

    void parseLine(const std::string& line, Request& request) const;
};

#endif // FILEREQUESTPROVIDER_H
