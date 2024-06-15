#ifndef REQUEST_H
#define REQUEST_H

#include <string>

struct Request {
    std::string process;
    double requestedTokens;
    double requestTimestamp;
    pid_t sleepPid;
    double waitTime;
};

#endif // REQUEST_H
