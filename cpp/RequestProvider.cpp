#include <vector>
#include <string>

struct Request {
    std::string process;
    double requestedTokens;
    double requestTimestamp;
    pid_t sleepPid;
    double waitTime;
};

class RequestProvider {
public:
    virtual std::vector<Request> getRequests() = 0;
    virtual ~RequestProvider() = default;
};
