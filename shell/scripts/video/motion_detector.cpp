#include <fstream>
#include <map>
#include <sstream>
#include <string>
#include <stdexcept>
#include <iostream>
#include <variant>
#include <opencv2/opencv.hpp>
#include <filesystem>
#include <vector>
#include <algorithm>
#include <cstdlib>

namespace fs = std::filesystem;



class Config {
public:
    static constexpr double DEFAULT_MOTION_THRESHOLD = 2.5;
    static constexpr int DEFAULT_FRAME_STEP = 20;
    static constexpr double DEFAULT_SECONDS_BEFORE = 1.0;
    static constexpr double DEFAULT_SECONDS_AFTER = 4.0;
    static constexpr int DEFAULT_BOUNDING_BOX_X = 0;
    static constexpr int DEFAULT_BOUNDING_BOX_Y = 0;
    static constexpr int DEFAULT_BOUNDING_BOX_WIDTH = 1400;
    static constexpr int DEFAULT_BOUNDING_BOX_HEIGHT = 900;
    static constexpr const char* DEFAULT_OUTPUT_PATH = "/home/user/WORK/tmp/vid/";

    Config(const std::string& configFilePath = "") {
        if (!configFilePath.empty() && std::filesystem::exists(configFilePath)) {
            loadConfig(configFilePath);
        }
        parseConfig();
    }

    double getMotionThreshold() const {
        return std::get<double>(parsedValues.at("motion_threshold"));
    }

    int getFrameStep() const {
        return std::get<int>(parsedValues.at("frame_step"));
    }

    double getSecondsBefore() const {
        return std::get<double>(parsedValues.at("seconds_before"));
    }

    double getSecondsAfter() const {
        return std::get<double>(parsedValues.at("seconds_after"));
    }

    void getBoundingBox(int (&boundingBox)[4]) const {
        boundingBox[0] = std::get<int>(parsedValues.at("bounding_box_x"));
        boundingBox[1] = std::get<int>(parsedValues.at("bounding_box_y"));
        boundingBox[2] = std::get<int>(parsedValues.at("bounding_box_width"));
        boundingBox[3] = std::get<int>(parsedValues.at("bounding_box_height"));
    }

    std::string getOutputPath() const {
        return std::get<std::string>(parsedValues.at("segment_output_path"));
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

    void parseConfig() {
        parsedValues["motion_threshold"] = getValue("motion_threshold", DEFAULT_MOTION_THRESHOLD);
        parsedValues["frame_step"] = getValue("frame_step", DEFAULT_FRAME_STEP);
        parsedValues["seconds_before"] = getValue("seconds_before", DEFAULT_SECONDS_BEFORE);
        parsedValues["seconds_after"] = getValue("seconds_after", DEFAULT_SECONDS_AFTER);
        parsedValues["bounding_box_x"] = getValue("bounding_box_x", DEFAULT_BOUNDING_BOX_X);
        parsedValues["bounding_box_y"] = getValue("bounding_box_y", DEFAULT_BOUNDING_BOX_Y);
        parsedValues["bounding_box_width"] = getValue("bounding_box_width", DEFAULT_BOUNDING_BOX_WIDTH);
        parsedValues["bounding_box_height"] = getValue("bounding_box_height", DEFAULT_BOUNDING_BOX_HEIGHT);
        parsedValues["segment_output_path"] = getValue("segment_output_path", std::string(DEFAULT_OUTPUT_PATH));
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
};



class VideoProcessor {
public:
    VideoProcessor(const std::string& videoPath, const Config& config)
        : videoPath(videoPath), config(config) {}

    void process() {
        std::string convertedVideoPath = convertToMP4(videoPath);

        if (convertedVideoPath.empty()) {
            std::cerr << "Error converting video file: " << videoPath << std::endl;
            return;
        }

        if (!cap.open(convertedVideoPath)) {
            std::cerr << "Error opening converted video file: " << convertedVideoPath << std::endl;
            return;
        }

        std::cout << "Video opened successfully." << std::endl;

        detectMotion();
        if (!motionSegments.empty()) {
            extractSegments(convertedVideoPath);
        }

        if (fs::exists(convertedVideoPath)) {
            fs::remove(convertedVideoPath);
            std::cout << "Converted video file deleted: " << convertedVideoPath << std::endl;
        }
    }

private:
    std::string videoPath;
    const Config& config;
    cv::VideoCapture cap;
    std::vector<std::pair<double, double>> motionSegments;

    std::string convertToMP4(const std::string& inputFilePath) {
        fs::path inputPath(inputFilePath);
        fs::path outputDir = inputPath.parent_path();
        std::string outputFileName = inputPath.stem().string() + "_converted.mp4";
        fs::path outputFilePath = outputDir / outputFileName;

        if (fs::exists(outputFilePath)) {
            return outputFilePath.string();
        }

        std::string command = "ffmpeg -y -loglevel error -i \"" + inputFilePath + "\" -c:v copy \"" + outputFilePath.string() + "\"";
        std::cout << "Converting video to MP4 format:\n" << command << std::endl;
        int ret = std::system(command.c_str());

        if (ret != 0) {
            std::cerr << "Error converting video file: " << inputFilePath << std::endl;
            return "";
        }

        return outputFilePath.string();
    }

    void detectMotion() {
        cv::Mat prevFrame, currFrame, frameDiff;
        double motionStartTime = -1;
        int frameIndex = 0;
        double fps = cap.get(cv::CAP_PROP_FPS);

        if (fps <= 0) {
            std::cerr << "Error retrieving FPS from video." << std::endl;
            return;
        }

        std::cout << "Starting to detect motion" << std::endl;

        int boundingBox[4];
        config.getBoundingBox(boundingBox);

        while (true) {
            cap.set(cv::CAP_PROP_POS_FRAMES, frameIndex);
            if (!cap.read(currFrame)) break;

            double nativeTime = (frameIndex / fps) * 1000.0;
            double prevTime = nativeTime / 1000.0;

            cv::cvtColor(currFrame, currFrame, cv::COLOR_BGR2GRAY);

            cv::Mat roi(currFrame, cv::Rect(boundingBox[0], boundingBox[1], boundingBox[2], boundingBox[3]));

            if (!prevFrame.empty()) {
                cv::Mat prevRoi(prevFrame, cv::Rect(boundingBox[0], boundingBox[1], boundingBox[2], boundingBox[3]));
                cv::absdiff(prevRoi, roi, frameDiff);
                double motionScore = cv::sum(frameDiff)[0] / (frameDiff.rows * frameDiff.cols);

                if (prevTime > 1.0 && motionScore > config.getMotionThreshold()) {
                    double lastMotionTime = prevTime;
                    if (motionStartTime < 0) {
                        std::cout << motionScore << " > " << config.getMotionThreshold() << " -> starting recording at: " << motionStartTime << " / nativeTime: " << nativeTime << " last motion time: " << lastMotionTime << std::endl;
                        motionStartTime = std::max(prevTime - config.getSecondsBefore(), 0.0);
                    } else {
                        std::cout << motionScore << " > " << config.getMotionThreshold() << " -> bump recording at: " << motionStartTime << " / nativeTime: " << nativeTime << " last motion time: " << lastMotionTime << std::endl;
                    }
                } else if (motionStartTime >= 0 && (prevTime - lastMotionTime) > config.getSecondsAfter()) {
                    double videoLength = frameIndex / fps;
                    double motionEndTime = std::min(prevTime + 1.0, videoLength);
                    std::cout << motionScore << " > " << config.getMotionThreshold() << " -> stop recording at: " << motionEndTime << " / nativeTime: " << nativeTime << std::endl;
                    motionSegments.emplace_back(motionStartTime, motionEndTime);
                    motionStartTime = -1;
                }
            }

            prevFrame = currFrame.clone();
            frameIndex += config.getFrameStep();
        }

        if (motionStartTime >= 0) {
            double videoLength = frameIndex / fps;
            double motionEndTime = std::min(prevTime + 1.0, videoLength);
            std::cout << motionScore << " > " << config.getMotionThreshold() << " -> stop recording at: " << motionEndTime << " / nativeTime: " << nativeTime << std::endl;
            motionSegments.emplace_back(motionStartTime, motionEndTime);
            motionStartTime = -1;
        }
    }

    void extractSegments(const std::string& convertedVideoPath) {
        for (const auto& segment : motionSegments) {
            extractSegmentWithFFmpeg(convertedVideoPath, segment.first, segment.second, generateOutputFilename(segment.first, segment.second));
        }
    }

    std::string generateOutputFilename(double start, double end) {
        fs::path videoFilePath(videoPath);
        fs::path outputFilePath(config.getOutputPath());

        fs::path dirPath = outputFilePath;
        std::string baseName = videoFilePath.stem().string();
        std::string extension = videoFilePath.extension().string();

        std::string newFilename = baseName + "_" + std::to_string(start) + "_" + std::to_string(end) + extension;
        fs::path fullPath = dirPath / newFilename;

        return fullPath.string();
    }

    static void extractSegmentWithFFmpeg(const std::string& inputFile, double start, double end, const std::string& outputFile) {
        double duration = end - start;
        std::string command = "ffmpeg -y -loglevel error -ss " + std::to_string(start) + " -i \"" + inputFile +
                              "\" -t " + std::to_string(duration) + " -c copy \"" + outputFile + "\"";
        std::cout << "Executing ffmpeg for segment: [" << start << " -> " << end << "]\n" << command << std::endl;
        std::system(command.c_str());
    }
};

int main(int argc, char** argv) {
    if (argc < 3 || argc > 4) {
        std::cerr << "Usage: " << argv[0] << " <video_path> <segment_output_path> [config_file_path]" << std::endl;
        return 1;
    }

    std::string videoPath = argv[1];
    std::string outputPath = argv[2];
    std::string configFilePath = (argc == 4) ? argv[3] : "";

    try {
        Config config(configFilePath);
        config.logConfig();

        VideoProcessor processor(videoPath, config);
        processor.process();
    } catch (const std::exception& e) {
        std::cerr << "Error reading configuration: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}


