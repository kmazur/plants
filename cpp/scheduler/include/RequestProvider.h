#ifndef REQUESTPROVIDER_H
#define REQUESTPROVIDER_H

#include <vector>
#include "Request.h"

class RequestProvider {
public:
    virtual std::vector<Request>& getRequests() const = 0;
    virtual void markRequestFulfilled(const std::string& process) = 0;
    virtual ~RequestProvider() = default;
};

#endif // REQUESTPROVIDER_H
