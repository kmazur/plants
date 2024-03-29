#include <opencv2/opencv.hpp>
#include <iostream>

int main(int argc, char** argv) {
         // Check if an image file path has been provided
    if(argc != 2) {
        std::cerr << "Usage: " << argv[0] << " <ImagePath>" << std::endl;
        return -1;
    }

    // Load the image from the provided file path
    cv::Mat image = cv::imread(argv[1], cv::IMREAD_GRAYSCALE);
    if(image.empty()) {
        std::cerr << "Failed to load image" << std::endl;
        return -1;
    }

    // Calculate the average brightness
    cv::Scalar avgPixelIntensity = cv::mean(image);
    std::cout << avgPixelIntensity[0] << std::endl;

    return 0;
}