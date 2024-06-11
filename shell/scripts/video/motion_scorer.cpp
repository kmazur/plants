#include <fstream>
#include <map>
#include <sstream>
#include <string>
#include <iostream>
#include <variant>
#include <opencv2/opencv.hpp>
#include <filesystem>
#include <vector>
#include <algorithm>

namespace fs = std::filesystem;

// Helper structure to store motion data
struct MotionData {
    double time;  // Time in milliseconds
    int frameIndex;
    double motionScore;
};

class Config {
public:
    static constexpr int DEFAULT_FRAME_STEP = 20;
    static constexpr const char* DEFAULT_POLYGON = "0,0;1400,0;1400,900;0,900";

    Config(const std::string& configFilePath = "") {
        if (!configFilePath.empty() && fs::exists(configFilePath)) {
            loadConfig(configFilePath);
        }
        parseConfig();
    }

    int getFrameStep() const {
        return std::get<int>(parsedValues.at("frame_step"));
    }

    const std::vector<cv::Point>& getPolygon() const {
        return polygon;
    }

    void logConfig() const {
        std::cout << "Configuration Parameters:" << std::endl;
        for (const auto& [key, value] : parsedValues) {
            std::visit([&key](auto&& val) {
                std::cout << key << " = " << val << std::endl;
            }, value);
        }
    }

private:
    std::map<std::string, std::string> config;
    std::map<std::string, std::variant<int, double, std::string>> parsedValues;
    std::vector<cv::Point> polygon;

    void loadConfig(const std::string& configFilePath) {
        std::ifstream configFile(configFilePath);
        std::string line;

        while (std::getline(configFile, line)) {
            std::istringstream lineStream(line);
            std::string key, value;
            if (std::getline(lineStream, key, '=') && std::getline(lineStream, value)) {
                config[key] = value;
            }
        }
    }

    void loadPolygon(const std::string& polygonStr) {
        std::istringstream ss(polygonStr);
        std::string pointStr;
        while (std::getline(ss, pointStr, ';')) {
            int x, y;
            std::sscanf(pointStr.c_str(), "%d,%d", &x, &y);
            polygon.emplace_back(cv::Point(x, y));
        }
    }

    void parseConfig() {
        parsedValues["frame_step"] = getValue("frame_step", DEFAULT_FRAME_STEP);
        std::string polygonStr = getValue<std::string>("polygon", DEFAULT_POLYGON);
        loadPolygon(polygonStr);
    }

    template <typename T>
    T getValue(const std::string& key, const T& defaultValue) const {
        auto it = config.find(key);
        if (it != config.end()) {
            std::istringstream ss(it->second);
            T value;
            ss >> value;
            if (ss.fail()) {
                throw std::runtime_error("Invalid value for key: " + key);
            }
            return value;
        }
        return defaultValue;
    }

    std::string getValue(const std::string& key, const std::string& defaultValue) const {
        auto it = config.find(key);
        if (it != config.end()) {
            return it->second;
        }
        return defaultValue;
    }
};

class VideoProcessor {
public:
    VideoProcessor(const std::string& videoPath, const std::string& outputPath, const Config& config)
        : videoPath(videoPath), outputPath(outputPath), config(config) {}

    void process() {
        if (!cap.open(videoPath)) {
            std::cerr << "Error opening video file: " << videoPath << std::endl;
            return;
        }
        std::cout << "Video opened successfully." << std::endl;

        detectMotion();
    }

private:
    std::string videoPath;
    std::string outputPath;
    const Config& config;
    cv::VideoCapture cap;
    double videoFps;

    void ensureSizeAndType(cv::Mat& mat, const cv::Size& size, int type) {
        if (mat.empty() || mat.size() != size || mat.type() != type) {
            mat.create(size, type);
        }
    }

    void detectMotion() {
        cv::Mat prevFrame, currFrame, frameDiff;
        cv::Mat prevFrameGray;
        double fps = cap.get(cv::CAP_PROP_FPS);

        videoFps = fps;

        if (fps <= 0) {
            std::cerr << "Error retrieving FPS from video." << std::endl;
            return;
        }

        std::cout << "Starting to score frames with motion detector" << std::endl;

        const std::vector<cv::Point>& polygon = config.getPolygon();
        cv::Rect boundingRect = cv::boundingRect(polygon);

        // Ensure boundingRect is within the frame dimensions
        int frameWidth = cap.get(cv::CAP_PROP_FRAME_WIDTH);
        int frameHeight = cap.get(cv::CAP_PROP_FRAME_HEIGHT);


        boundingRect &= cv::Rect(0, 0, frameWidth, frameHeight);

        // Adjust the polygon points if necessary
        std::vector<cv::Point> adjustedPolygon;
        std::transform(polygon.begin(), polygon.end(), std::back_inserter(adjustedPolygon), [&boundingRect](const cv::Point& p) {
            return cv::Point(std::clamp(p.x, boundingRect.x, boundingRect.x + boundingRect.width),
                             std::clamp(p.y, boundingRect.y, boundingRect.y + boundingRect.height));
        });

        cv::Mat mask = cv::Mat::zeros(boundingRect.size(), CV_8UC1);
        std::vector<cv::Point> relativePolygon(adjustedPolygon.size());

        std::transform(adjustedPolygon.begin(), adjustedPolygon.end(), relativePolygon.begin(), [&boundingRect](const cv::Point& p) {
            return p - boundingRect.tl();
        });
        cv::fillPoly(mask, std::vector<std::vector<cv::Point>>{relativePolygon}, cv::Scalar(255));

        cv::Mat currRoi, prevRoi, maskedDiff;
        ensureSizeAndType(currRoi, boundingRect.size(), CV_8UC1);

        double frameTimeSecond = 0.0;
        int frameIndex = 0;
        int frameIndexStep = config.getFrameStep();

        double frameTimeIncrement = 1.0 / fps;
        double stepTimeIncrement = frameIndexStep * frameTimeIncrement;

        double frameCount = cap.get(cv::CAP_PROP_FRAME_COUNT);

        std::cout << "Diagnostics: " <<
        "\nFPS: " << fps <<
        "\nwidth: " << frameWidth <<
        "\nheight: " << frameHeight <<
        "\nframeStep: " << frameIndexStep <<
        "\nframeTimeIncrement: " << frameTimeIncrement <<
        "\nstepTimeIncrement: " << stepTimeIncrement <<
        "\nframeCount: " << frameCount <<
        "\n";

        std::vector<MotionData> motionDataList;

        ensureSizeAndType(currRoi, boundingRect.size(), CV_8UC1);
        ensureSizeAndType(prevRoi, boundingRect.size(), CV_8UC1);
        ensureSizeAndType(frameDiff, boundingRect.size(), CV_8UC1);
        ensureSizeAndType(maskedDiff, boundingRect.size(), CV_8UC1);

        while (true) {
            cap.set(cv::CAP_PROP_POS_FRAMES, frameIndex);
            if (!cap.read(currFrame)) {
                break;
            }

            cv::cvtColor(currFrame(boundingRect), currRoi, cv::COLOR_BGR2GRAY);

            if (!prevFrame.empty()) {
                cv::absdiff(prevRoi, currRoi, frameDiff);
                frameDiff.copyTo(maskedDiff, mask);
                double motionScore = cv::sum(maskedDiff)[0] / cv::countNonZero(mask);
                std::cout << "Frame: " << frameIndex << " (" << (100 * frameIndex / frameCount) << "%), frame score: " << motionScore << "\n";

                motionDataList.push_back({frameTimeSecond, frameIndex, motionScore});
            }

            std::swap(prevFrame, currFrame);
            std::swap(prevRoi, currRoi);
            frameIndex += frameIndexStep;

            frameTimeSecond += stepTimeIncrement;
        }

        writeMotionDataToFile(motionDataList);
    }

    void writeMotionDataToFile(const std::vector<MotionData>& motionDataList) {
        std::ofstream file(outputPath);
        if (!file.is_open()) {
            std::cerr << "Failed to open file for writing: " << outputPath << std::endl;
            return;
        }

        for (const auto& data : motionDataList) {
            file << data.frameIndex << " " << data.time << " " << data.motionScore << "\n";
        }
        file.close();
    }
};

int main(int argc, char** argv) {
    if (argc < 3 || argc > 4) {
        std::cerr << "Usage: " << argv[0] << " <video_path> <score_file_path> [config_file_path]" << std::endl;
        return 1;
    }

    std::string videoPath = argv[1];
    std::string outputPath = argv[2];
    std::string configFilePath = (argc == 4) ? argv[3] : "";

    try {
        Config config(configFilePath);
        config.logConfig();

        VideoProcessor processor(videoPath, outputPath, config);
        processor.process();
    } catch (const std::exception& e) {
        std::cerr << "Error reading configuration: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}
