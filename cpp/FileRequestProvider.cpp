#include <fstream>
#include <sstream>

class FileRequestProvider : public RequestProvider {
public:
    FileRequestProvider(const std::string& filePath) : filePath(filePath) {}

    std::vector<Request> getRequests() override {
        std::vector<Request> requests;
        std::ifstream infile(filePath);
        std::string line;

        while (std::getline(infile, line)) {
            std::istringstream ss(line);
            std::string process, tokensStr, pidStr, datetime;

            std::getline(ss, process, '=');
            std::getline(ss, tokensStr, ':');
            std::getline(ss, pidStr, ':');
            std::getline(ss, datetime);

            Request request;
            request.process = process;
            request.requestedTokens = std::stod(tokensStr);
            request.sleepPid = std::stoi(pidStr);
            request.requestTimestamp = dateCompactToEpoch(datetime);
            request.waitTime = std::time(nullptr) - request.requestTimestamp;

            requests.push_back(request);
        }

        return requests;
    }

private:
    std::string filePath;
};
