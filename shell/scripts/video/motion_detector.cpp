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

namespace fs = std::filesystem;

class VideoProcessor {
public:
    VideoProcessor(const std::string& videoPath, const std::string& outputPath) : videoPath(videoPath), outputPath(outputPath) {}

    void process() {
        if (!cap.open(videoPath)) {
            std::cerr << "Error opening video file: " << videoPath << std::endl;
            return;
        }

        detectMotion();
        if (!motionSegments.empty()) {
            extractSegments();
        }
    }

private:
    std::string videoPath;
    std::string outputPath;
    cv::VideoCapture cap;
    std::vector<std::pair<double, double>> motionSegments; // Stores start and end times of motion segments

    static constexpr double motionThreshold = 0.0095; // Example threshold, adjust based on your needs
    static constexpr int frameStep = 20; // Analyze every 20th frame for motion

    void detectMotion() {
        cv::Mat prevFrame, currFrame, frameDiff;
        double motionStartTime = -1;
        int frameIndex = 0;

        while (cap.read(currFrame)) {
            double prevTime = cap.get(cv::CAP_PROP_POS_MSEC) / 1000.0; // Time in seconds

            cv::cvtColor(currFrame, currFrame, cv::COLOR_BGR2GRAY);
            if (!prevFrame.empty()) {
                cv::absdiff(prevFrame, currFrame, frameDiff);
                double motionScore = cv::sum(frameDiff)[0] / (frameDiff.rows * frameDiff.cols); // Normalize motion score

                if (motionScore > motionThreshold) {
                    if (motionStartTime < 0) motionStartTime = std::max(prevTime - 1.0, 0.0); // Mark start of motion
                } else if (motionStartTime >= 0) {
                    double videoLength = cap.get(cv::CAP_PROP_POS_MSEC) / 1000.0;
                    motionSegments.emplace_back(motionStartTime, std::min(prevTime + 1.0, videoLength)); // End of motion segment
                    motionStartTime = -1; // Reset for next motion segment
                }
            }

            prevFrame = currFrame.clone();
            frameIndex += frameStep; // Jump to the next frame
            cap.set(cv::CAP_PROP_POS_FRAMES, frameIndex);
        }
    }

    void extractSegments() {
        for (const auto& segment : motionSegments) {
            extractSegmentWithFFmpeg(videoPath, segment.first, segment.second, generateOutputFilename(segment.first, segment.second));
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
        std::string command = "ffmpeg -y -loglevel error -ss " + std::to_string(start) + " -i \"" + inputFile +
                              "\" -to " + std::to_string(end - start) + " -c copy \"" + outputFile + "\"";
        std::system(command.c_str());
    }
};

int main(int argc, char** argv) {
    if (argc < 3) {
        std::cerr << "Usage: " << argv[0] << " <video_path> <segment_output_path>" << std::endl;
        return 1;
    }
    std::string videoPath = argv[1];
    std::string outputPath = argv[2];
    VideoProcessor processor(videoPath, outputPath);
    processor.process();

    return 0;
}