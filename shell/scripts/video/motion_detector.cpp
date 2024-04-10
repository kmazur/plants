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
#include <thread>
#include <future>
#include <mutex>
#include <vector>

namespace fs = std::filesystem;

class VideoProcessor {
public:
    VideoProcessor(const std::string& videoPath) : videoPath(videoPath) {}

    void process() {
        if (!cap.open(videoPath)) {
            std::cerr << "Error opening video file: " << videoPath << std::endl;
            return;
        }

        detectMotionConcurrently();
        if (!motionSegments.empty()) {
            extractSegmentsConcurrently();
        }
    }

private:
    std::string videoPath;
    cv::VideoCapture cap;
    std::vector<std::pair<double, double>> motionSegments; // Stores start and end times of motion segments
    std::mutex motionSegmentsMutex; // Mutex for thread-safe access to motionSegments

    static constexpr double motionThreshold = 0.0095; // Example threshold, adjust based on your needs
    static constexpr int frameStep = 20; // Analyze every 20th frame for motion

    void detectMotionConcurrently() {
        size_t threadCount = std::thread::hardware_concurrency();
        std::vector<std::future<void>> futures;
        for (size_t i = 0; i < threadCount; ++i) {
            futures.emplace_back(std::async(std::launch::async, &VideoProcessor::detectMotion, this, i, threadCount));
        }
        for (auto& future : futures) {
            future.wait();
        }
    }

    void detectMotion(size_t threadId, size_t threadCount) {
        cv::Mat prevFrame, currFrame, frameDiff;
        double prevTime = 0, motionStartTime = -1;
        int frameIndex = 0;

        // Adjust reading to only handle frames for this thread
        while (true) {
            cap.set(cv::CAP_PROP_POS_FRAMES, frameIndex * frameStep + threadId * frameStep / threadCount);
            if (!cap.read(currFrame)) return; // Break the loop if no more frames
            prevTime = cap.get(cv::CAP_PROP_POS_MSEC) / 1000.0; // Time in seconds

            cv::cvtColor(currFrame, currFrame, cv::COLOR_BGR2GRAY);
            if (!prevFrame.empty()) {
                cv::absdiff(prevFrame, currFrame, frameDiff);
                double motionScore = cv::sum(frameDiff)[0] / (frameDiff.rows * frameDiff.cols); // Normalize motion score

                if (motionScore > motionThreshold) {
                    if (motionStartTime < 0) motionStartTime = std::max(prevTime - 1.0, 0.0); // Mark start of motion
                } else if (motionStartTime >= 0) {
                    double videoLength = cap.get(cv::CAP_PROP_POS_MSEC) / 1000.0;
                    std::lock_guard<std::mutex> guard(motionSegmentsMutex);
                    motionSegments.emplace_back(motionStartTime, std::min(prevTime + 1.0, videoLength)); // End of motion segment
                    motionStartTime = -1; // Reset for next motion segment
                }
            }

            currFrame.copyTo(prevFrame);
            frameIndex += threadCount; // Jump to the next frame this thread is responsible for
        }
    }

    void extractSegmentsConcurrently() {
        std::vector<std::future<void>> futures;
        for (const auto& segment : motionSegments) {
            futures.emplace_back(std::async(std::launch::async, &VideoProcessor::extractSegmentWithFFmpeg, videoPath, segment.first, segment.second, generateOutputFilename(segment.first, segment.second)));
        }
        for (auto& future : futures) {
            future.wait();
        }
    }

    std::string generateOutputFilename(double start, double end) {
            // Get the full path of the video file
            fs::path videoFilePath(videoPath);

            // Extract the directory, base name, and extension of the video file
            fs::path dirPath = videoFilePath.parent_path();
            std::string baseName = videoFilePath.stem().string();
            std::string extension = videoFilePath.extension().string();

            // Construct the new filename with start and end times
            std::string newFilename = baseName + "_" + std::to_string(start) + "_" + std::to_string(end) + extension;

            // Combine the directory path with the new filename to preserve the directory location
            fs::path outputPath = dirPath / newFilename;

            return outputPath.string();
    }

    static void extractSegmentWithFFmpeg(const std::string& inputFile, double start, double end, const std::string& outputFile) {
        // Construct and execute FFmpeg command
        std::string command = "ffmpeg -y -loglevel error -ss " + std::to_string(start) + " -i \"" + inputFile +
                              "\" -to " + std::to_string(end - start) + " -c copy \"" + outputFile + "\"";
        std::system(command.c_str());
    }
};

int main(int argc, char** argv) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <video_path>" << std::endl;
        return 1;
    }
    std::string videoPath = argv[1];
    VideoProcessor processor(videoPath);
    processor.process();

    return 0;
}