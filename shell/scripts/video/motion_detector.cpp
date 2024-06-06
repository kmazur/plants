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

// Helper structure to store motion data
struct MotionData {
    double time;  // Time in milliseconds
    int frameIndex;
    double motionScore;
};

class Config {
public:
    static constexpr double DEFAULT_MOTION_THRESHOLD = 2.5;
    static constexpr int DEFAULT_FRAME_STEP = 20;
    static constexpr double DEFAULT_SECONDS_BEFORE = 1.0;
    static constexpr double DEFAULT_SECONDS_AFTER = 4.0;
    static constexpr const char* DEFAULT_POLYGON = "0,0;1400,0;1400,900;0,900";

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
        parsedValues["motion_threshold"] = getValue("motion_threshold", DEFAULT_MOTION_THRESHOLD);
        parsedValues["frame_step"] = getValue("frame_step", DEFAULT_FRAME_STEP);
        parsedValues["seconds_before"] = getValue("seconds_before", DEFAULT_SECONDS_BEFORE);
        parsedValues["seconds_after"] = getValue("seconds_after", DEFAULT_SECONDS_AFTER);

        std::string polygonStr = getValue<std::string>("polygon", DEFAULT_POLYGON);
        loadPolygon(polygonStr);
    }

   // General template method for non-string types
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

    // Template specialization for string types
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
    std::string outputPath;
    const Config& config;
    cv::VideoCapture cap;
    std::vector<std::pair<double, double>> motionSegments;
    double videoFps;

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

    // Helper method to ensure size and type of a matrix
    void ensureSizeAndType(cv::Mat& mat, const cv::Size& size, int type) {
        if (mat.empty() || mat.size() != size || mat.type() != type) {
            mat.create(size, type);
        }
    }

    void detectMotion() {
        cv::Mat prevFrame, currFrame, frameDiff;
        cv::Mat prevFrameGray;
        double motionStartTime = -1;
        int frameIndex = 0;
        double fps = cap.get(cv::CAP_PROP_FPS);
        videoFps = fps;

        if (fps <= 0) {
            std::cerr << "Error retrieving FPS from video." << std::endl;
            return;
        }

        std::cout << "Starting to detect motion" << std::endl;

        const std::vector<cv::Point>& polygon = config.getPolygon();
        cv::Rect boundingRect = cv::boundingRect(polygon);

        // Pre-allocate mask and adjustedPolygon
        cv::Mat mask = cv::Mat::zeros(boundingRect.size(), CV_8UC1);
        std::vector<cv::Point> adjustedPolygon(polygon.size());

        std::transform(polygon.begin(), polygon.end(), adjustedPolygon.begin(), [&boundingRect](const cv::Point& p) {
            return p - boundingRect.tl();
        });
        cv::fillPoly(mask, std::vector<std::vector<cv::Point>>{adjustedPolygon}, cv::Scalar(255));

        // Pre-allocate memory for regions and differences
        cv::Mat roi, prevRoi, maskedDiff;
        double lastMotionTime = 0.0;
        double prevTime = 0.0;

        double ignoreFirstSeconds = 1.0;

        std::vector<MotionData> motionDataList;

        while (true) {
            cap.set(cv::CAP_PROP_POS_FRAMES, frameIndex);
            if (!cap.read(currFrame)) break;

            double nativeTime = (frameIndex / fps) * 1000.0;
            prevTime = nativeTime / 1000.0;

            // Check if the frame is non-empty and the size is valid
            if (currFrame.empty() || currFrame.cols < boundingRect.width || currFrame.rows < boundingRect.height) {
                std::cerr << "Error: Current frame is invalid or too small." << std::endl;
                break;
            }

            // Convert to grayscale only within the ROI
            ensureSizeAndType(roi, boundingRect.size(), CV_8UC1);
            // Log ROI details
            cv::cvtColor(currFrame(boundingRect), roi, cv::COLOR_BGR2GRAY);

            if (!prevFrame.empty()) {
                // Ensure prevFrameGray is the correct size and type before converting
                ensureSizeAndType(prevFrameGray, boundingRect.size(), CV_8UC1);
                cv::cvtColor(prevFrame(boundingRect), prevFrameGray, cv::COLOR_BGR2GRAY);
                ensureSizeAndType(prevRoi, boundingRect.size(), CV_8UC1);
                prevFrameGray.copyTo(prevRoi);

                // Ensure the frameDiff matrix is the same size and type as the ROIs
                ensureSizeAndType(frameDiff, boundingRect.size(), CV_8UC1);

                // Check types and sizes before performing absdiff
                if (prevRoi.type() == roi.type() && prevRoi.size() == roi.size()) {
                    cv::absdiff(prevRoi, roi, frameDiff);
                } else {
                    std::cerr << "Error: prevRoi and roi must be the same size and type for absdiff." << std::endl;
                    break;
                }

                ensureSizeAndType(maskedDiff, boundingRect.size(), CV_8UC1);
                frameDiff.copyTo(maskedDiff, mask);

                double motionScore = cv::sum(maskedDiff)[0] / cv::countNonZero(mask);

                // Accumulate motion data if a segment is being recorded
                if (motionStartTime >= 0) {
                    motionDataList.push_back({prevTime - motionStartTime, frameIndex, motionScore});
                    std::cout << "time: " << prevTime - motionStartTime << ", frame: " << frameIndex << ", score: " << motionScore << std::endl;
                }

                if (prevTime > ignoreFirstSeconds) {
                    if (motionScore > config.getMotionThreshold()) {
                        lastMotionTime = prevTime;
                        if (motionStartTime < 0) {
                            motionStartTime = std::max(prevTime - config.getSecondsBefore(), 0.0);
                            std::cout << motionScore << " > " << config.getMotionThreshold() << " -> motion start detected at: " << motionStartTime << " s " << std::endl;
                            motionDataList.clear();
                            motionDataList.push_back({0.0, frameIndex, motionScore});
                            std::cout << "time: " << prevTime - motionStartTime << ", frame: " << frameIndex << ", score: " << motionScore << std::endl;
                        } else {
                            std::cout << motionScore << " > " << config.getMotionThreshold() << " -> motion continuing from: " << motionStartTime << " -> " << prevTime << std::endl;
                        }
                    } else if (motionStartTime >= 0 && (prevTime - lastMotionTime) > config.getSecondsAfter()) {
                        double videoLength = frameIndex / fps;
                        double motionEndTime = std::min(lastMotionTime + 1.0, videoLength);
                        std::cout << motionScore << " > " << config.getMotionThreshold() << " -> motion end. Motion detected at: " << motionStartTime << " -> " << motionEndTime << std::endl;
                        motionSegments.emplace_back(motionStartTime, motionEndTime);
                        // Write the motion data to a file named after the segment
                        writeMotionDataToFile(motionStartTime, motionEndTime, motionDataList);
                        motionDataList.clear();
                        motionStartTime = -1;
                        break;
                    }
                }
            }

            // Efficient way to swap current and previous frames
            std::swap(prevFrame, currFrame);
            frameIndex += config.getFrameStep();
        }

        if (motionStartTime >= 0) {
            double videoLength = frameIndex / fps;
            double motionEndTime = std::min(lastMotionTime + 1.0, videoLength);
            std::cout << "?" << " > " << config.getMotionThreshold() << " -> motion end. Motion detected at: " << motionStartTime << " -> " << motionEndTime << std::endl;
            motionSegments.emplace_back(motionStartTime, motionEndTime);
            // Write the motion data to a file named after the last segment
            writeMotionDataToFile(motionStartTime, motionEndTime, motionDataList);
            motionDataList.clear();
            motionStartTime = -1;
        }
    }

    void writeMotionDataToFile(double startTime, double endTime, const std::vector<MotionData>& motionDataList) {
        std::string filename = generateOutputFilename(startTime, endTime) + ".scores";

        std::ofstream file(filename);
        if (!file.is_open()) {
            std::cerr << "Failed to open file for writing: " << filename << std::endl;
            return;
        }

        // Write each motion data entry with time and motion score in a format suitable for FFmpeg
        for (const auto& data : motionDataList) {
            file << data.time << " " << data.motionScore << "\n"; // Time in seconds and motion score
        }

        file.close();
        std::cout << "Motion data written to file: " << filename << std::endl;
    }

    void overlayMotionScores(const std::string& videoSegment, const std::string& scoresFile) {
        std::string outputFilename = videoSegment + "_with_scores.mp4";

        // Read the scores file
        std::ifstream file(scoresFile);
        if (!file.is_open()) {
            std::cerr << "Failed to open scores file: " << scoresFile << std::endl;
            return;
        }

        std::vector<MotionData> motionDataList;
        std::string line;
        while (std::getline(file, line)) {
            std::istringstream lineStream(line);
            double time;
            double score;
            lineStream >> time >> score;

            motionDataList.push_back({time, 0, score});
        }
        file.close();

        // Construct the drawtext command for each score with enable expressions
        std::ostringstream drawtextCommand;
        for (size_t i = 0; i < motionDataList.size(); ++i) {
            const auto& data = motionDataList[i];
            double nextTime = (i + 1 < motionDataList.size()) ? motionDataList[i + 1].time : data.time + 10; // assume 10s default for last segment
            drawtextCommand << "drawtext=fontfile=/path/to/font.ttf:text='Motion Score >" << data.motionScore
                            << "<':x=10:y=h-50:fontcolor=white:fontsize=24:box=1:boxcolor=black@0.5:boxborderw=5"
                            << ":enable='between(t," << data.time << "," << nextTime << ")',";
        }

        std::string drawtextFilters = drawtextCommand.str();
        if (!drawtextFilters.empty()) {
            drawtextFilters.pop_back(); // Remove the trailing comma
        }

        std::string command = "ffmpeg -y -i \"" + videoSegment + "\" -vf \"" + drawtextFilters + "\" -codec:a copy \"" + outputFilename + "\"";

        std::cout << "Executing FFmpeg command for overlay: " << command << std::endl;
        int ret = std::system(command.c_str());

        if (ret != 0) {
            std::cerr << "Error overlaying text on video segment: " << videoSegment << std::endl;
        } else {
            std::cout << "Video segment with scores created: " << outputFilename << std::endl;
        }
    }

    void overlayPolygon(const std::string& videoSegment) {
        const std::vector<cv::Point>& polygon = config.getPolygon();
        std::ostringstream coords;

        for (const auto& point : polygon) {
            coords << point.x << "," << point.y << " ";
        }

        // Create the polygon image using ImageMagick
        std::string polygonImage = "polygon.png";
        std::string command = "convert -size 1280x720 xc:transparent -fill none -stroke red -draw \"polygon " + coords.str() + "\" " + polygonImage;
        std::cout << "Creating polygon image: " << command << std::endl;
        int ret = std::system(command.c_str());

        if (ret != 0) {
            std::cerr << "Error creating polygon image." << std::endl;
            return;
        }

        // Overlay the polygon on the video using FFmpeg
        std::string outputFilename = videoSegment + "_with_polygon.mp4";
        command = "ffmpeg -y -i \"" + videoSegment + "\" -i " + polygonImage + " -filter_complex \"overlay\" -codec:a copy \"" + outputFilename + "\"";
        std::cout << "Overlaying polygon on video: " << command << std::endl;
        ret = std::system(command.c_str());

        if (ret != 0) {
            std::cerr << "Error overlaying polygon on video segment: " << videoSegment << std::endl;
        } else {
            std::cout << "Video segment with polygon created: " << outputFilename << std::endl;
        }

        // Clean up the temporary polygon image
        std::remove(polygonImage.c_str());
    }

    void extractSegments(const std::string& convertedVideoPath) {
        for (const auto& segment : motionSegments) {
            std::string outputSegment = generateOutputFilename(segment.first, segment.second);
            extractSegmentWithFFmpeg(convertedVideoPath, segment.first, segment.second, outputSegment);

            // Overlay the motion scores after extracting the segment
            std::string scoresFile = outputSegment + ".scores";
            overlayMotionScores(outputSegment, scoresFile);

            std::string scoresVideo = outputSegment + "_with_scores.mp4";
            overlayPolygon(scoresVideo)
        }
    }

    std::string generateOutputFilename(double start, double end) {
        fs::path videoFilePath(videoPath);
        fs::path outputFilePath(outputPath);

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

        VideoProcessor processor(videoPath, outputPath, config);
        processor.process();
    } catch (const std::exception& e) {
        std::cerr << "Error reading configuration: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}


