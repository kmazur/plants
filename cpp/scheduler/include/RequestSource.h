#ifndef REQUESTSOURCE_H
#define REQUESTSOURCE_H

#include <vector>
#include "Request.h"

class RequestSource
{
public:
    virtual const std::vector<Request> &getRequests() const = 0;
    virtual void markRequestFulfilled(const Request &process) = 0;
    virtual ~RequestSource() = default;
};

#endif // REQUESTSOURCE_H