#include <opencv2/opencv.hpp>
#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <filesystem>
#include <deque>
#include <numeric>
#include <algorithm>
#include <cstdlib>
#include <map>
#include <sstream>

namespace fs = std::filesystem;

class VideoProcessor {
public:
    VideoProcessor(const std::string& videoPath, const std::string& outputPath, double motionThreshold, int boundingBox[4], int frameStep, double secondsBefore, double secondsAfter)
        : videoPath(videoPath), outputPath(outputPath), motionThreshold(motionThreshold), frameStep(frameStep), secondsBefore(secondsBefore), secondsAfter(secondsAfter) {
        std::copy(boundingBox, boundingBox + 4, this->boundingBox);
    }
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

        // Clean up the converted video file
        if (!convertedVideoPath.empty() && fs::exists(convertedVideoPath)) {
            fs::remove(convertedVideoPath);
            std::cout << "Converted video file deleted: " << convertedVideoPath << std::endl;
        }
    }

private:
    std::string videoPath;
    std::string outputPath;
    cv::VideoCapture cap;
    std::vector<std::pair<double, double>> motionSegments; // Stores start and end times of motion segments

    int frameStep;
    double secondsBefore;
    double secondsAfter;
    double motionThreshold;
    int boundingBox[4]; // [x, y, width, height]

    std::string convertToMP4(const std::string& inputFilePath) {
        fs::path inputPath(inputFilePath);
        fs::path outputDir = inputPath.parent_path(); // Get the parent directory of the input file
        std::string outputFileName = inputPath.stem().string() + "_converted.mp4";
        fs::path outputFilePath = outputDir / outputFileName; // Combine the directory and the new file name

        if (fs::exists(outputFilePath.string())) {
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

        int frameWidth = currFrame.cols;
        int frameHeight = currFrame.rows;

        // Adjust bounding box to be within frame boundaries
        boundingBox[2] = std::min(boundingBox[2], frameWidth - boundingBox[0]);
        boundingBox[3] = std::min(boundingBox[3], frameHeight - boundingBox[1]);

        double nativeTime = 0.0;
        double prevTime = 0.0;
        double motionScore = 0.0;
        double lastMotionTime = 0.0;

        while (true) {
            cap.set(cv::CAP_PROP_POS_FRAMES, frameIndex);
            if (!cap.read(currFrame)) break;

            nativeTime = (frameIndex / fps) * 1000.0; // Computed native time in milliseconds
            prevTime = nativeTime / 1000.0; // Time in seconds

            cv::cvtColor(currFrame, currFrame, cv::COLOR_BGR2GRAY);

            // Apply bounding box
            cv::Mat roi(currFrame, cv::Rect(boundingBox[0], boundingBox[1], boundingBox[2], boundingBox[3]));

            if (!prevFrame.empty()) {
                cv::Mat prevRoi(prevFrame, cv::Rect(boundingBox[0], boundingBox[1], boundingBox[2], boundingBox[3]));
                cv::absdiff(prevRoi, roi, frameDiff);
                motionScore = cv::sum(frameDiff)[0] / (frameDiff.rows * frameDiff.cols); // Normalize motion score

                if (prevTime > 1.0 && motionScore > motionThreshold) {
                    lastMotionTime = prevTime;
                    if (motionStartTime < 0) {
                        std::cout << motionScore << " > " << motionThreshold << " -> starting recording at: " << motionStartTime << " / nativeTime: " << nativeTime << " last motion time: " << lastMotionTime << std::endl;
                        motionStartTime = std::max(prevTime - secondsBefore, 0.0);
                    } else {
                        std::cout << motionScore << " > " << motionThreshold << " -> bump recording at: " << motionStartTime << " / nativeTime: " << nativeTime << " last motion time: " << lastMotionTime << std::endl;
                    }
                } else if (motionStartTime >= 0 && (prevTime - lastMotionTime) > secondsAfter) {
                    double videoLength = frameIndex / fps; // Calculate video length in seconds
                    double motionEndTime = std::min(prevTime + 1.0, videoLength);
                    std::cout << motionScore << " > " << motionThreshold << " -> stop recording at: " << motionEndTime << " / nativeTime: " << nativeTime << std::endl;
                    motionSegments.emplace_back(motionStartTime, motionEndTime); // End of motion segment
                    motionStartTime = -1; // Reset for next motion segment
                }
            }

            prevFrame = currFrame.clone();
            frameIndex += frameStep; // Jump to the next frame
        }

        if (motionStartTime >= 0) {
            double videoLength = frameIndex / fps; // Calculate video length in seconds
            double motionEndTime = std::min(prevTime + 1.0, videoLength);
            std::cout << motionScore << " > " << motionThreshold << " -> stop recording at: " << motionEndTime << " / nativeTime: " << nativeTime << std::endl;
            motionSegments.emplace_back(motionStartTime, motionEndTime); // End of motion segment
            motionStartTime = -1; // Reset for next motion segment
        }
    }

    void extractSegments(const std::string& convertedVideoPath) {
        for (const auto& segment : motionSegments) {
            extractSegmentWithFFmpeg(convertedVideoPath, segment.first, segment.second, generateOutputFilename(segment.first, segment.second));
        }
    }

    std::string generateOutputFilename(double start, double end) {
            fs::path videoFilePath(videoPath);
            fs::path outputFilePath(outputPath);

            fs::path dirPath = outputFilePath.parent_path();
            std::string baseName = videoFilePath.stem().string();
            std::string extension = videoFilePath.extension().string();

            std::string newFilename = baseName + "_" + std::to_string(start) + "_" + std::to_string(end) + extension;
            fs::path outputPath = dirPath / newFilename;

            return outputPath.string();
    }

    static void extractSegmentWithFFmpeg(const std::string& inputFile, double start, double end, const std::string& outputFile) {
        double duration = end - start;
        std::string command = "ffmpeg -y -loglevel error -ss " + std::to_string(start) + " -i \"" + inputFile +
                              "\" -t " + std::to_string(duration) + " -c copy \"" + outputFile + "\"";
        std::cout << "Executing ffmpeg for segment: [" << start << " -> " << end << "]\n" << command << std::endl;
        std::system(command.c_str());
    }
};

std::map<std::string, std::string> readConfigFile(const std::string& configFilePath) {
    std::map<std::string, std::string> config;
    std::ifstream configFile(configFilePath);
    std::string line;

    while (std::getline(configFile, line)) {
        std::istringstream lineStream(line);
        std::string key, value;
        if (std::getline(lineStream, key, '=') && std::getline(lineStream, value)) {
            config[key] = value;
        }
    }

    return config;
}

template <typename T>
T getConfigValue(const std::map<std::string, std::string>& config, const std::string& key, const T& defaultValue) {
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

int main(int argc, char** argv) {
    if (argc != 3) {
        std::cerr << "Usage: " << argv[0] << " <video_path> <segment_output_path> <config_file_path>" << std::endl;
        return 1;
    }
    std::string videoPath = argv[1];
    std::string outputPath = argv[2];
    std::string configFilePath = argv[3];
    std::map<std::string, std::string> config = readConfigFile(configFilePath);

    try {
        std::string outputPath = getConfigValue(config, "segment_output_path", std::string("/home/user/WORK/tmp/vid/"));
        double motionThreshold = getConfigValue(config, "motion_threshold", 1.6);
        int boundingBox[4] = {
            getConfigValue(config, "bounding_box_x", 0),
            getConfigValue(config, "bounding_box_y", 0),
            getConfigValue(config, "bounding_box_width", 640),
            getConfigValue(config, "bounding_box_height", 480)
        };

        std::cout << "Parameters:\n" <<
            "threshold = " << motionThreshold << "\n" <<
            "boundingBox = [x: " << boundingBox[0] << ", y: " << boundingBox[1] << ", w: " << boundingBox[2] << ", h: " << boundingBox[3] << "]\n" << std::endl;

        VideoProcessor processor(videoPath, outputPath, motionThreshold, boundingBox);
        processor.process();
    } catch (const std::exception& e) {
        std::cerr << "Error reading configuration: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}
