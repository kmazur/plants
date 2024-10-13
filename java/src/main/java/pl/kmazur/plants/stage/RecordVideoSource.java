package pl.kmazur.plants.stage;

import lombok.NonNull;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.opencv.core.Core;
import org.opencv.core.Mat;
import org.opencv.core.Scalar;
import org.opencv.imgcodecs.Imgcodecs;
import org.opencv.imgproc.Imgproc;
import pl.kmazur.plants.camera.Camera;
import pl.kmazur.plants.config.AppConfig;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.util.LinkedList;
import java.util.Queue;
import java.util.concurrent.Flow.Publisher;
import java.util.concurrent.Flow.Subscriber;
import java.util.concurrent.Flow.Subscription;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

@Slf4j
@RequiredArgsConstructor
public class RecordVideoSource  {

    private final AppConfig config;
    private final Camera camera = new Camera();

    private final Queue<VideoOutput> queue = new LinkedBlockingQueue<>();

//
//    public void doRun() {
//        int segmentDurationSeconds = config.getInt("video.segment_duration_seconds", 300);
//        String videoConfigFile = config.get("video-config-file");
//        String imageConfigFile = config.get("image-config-file");
//
//        log.info("Capturing image");
//        String snapshotPath = getTimestampedFilePath("snapshot", "jpg");
//        camera.captureImage(imageConfigFile, snapshotPath);
//
//        double averagePixel = getAveragePixel(snapshotPath);
//        log.info("Light level is: {}", averagePixel);
//        String lightLevelPath = getTimestampedFilePath("light_level", "txt");
//        try {
//            Files.writeString(Paths.get(lightLevelPath), Double.toString(averagePixel), StandardOpenOption.CREATE, StandardOpenOption.WRITE);
//        } catch (IOException e) {
//            throw new UncheckedIOException(e);
//        }
//
//        if (averagePixel < 5) {
//            log.info("Light level is too low to record video");
//            return;
//        }
//
//        log.info("Recording video for {} seconds", segmentDurationSeconds);
//        String videoPath = getTimestampedFilePath("video", "h264");
//        camera.recordVideo(videoConfigFile, videoPath, segmentDurationSeconds, TimeUnit.SECONDS);
//    }
//
//    private static double getAveragePixel(String snapshotPath) {
//        Mat image = Imgcodecs.imread(snapshotPath);
//        Mat grayImage = new Mat();
//        Imgproc.cvtColor(image, grayImage, Imgproc.COLOR_BGR2GRAY);
//        Scalar avgPixelIntensity = Core.mean(grayImage);
//
//        return avgPixelIntensity.val[0];
//    }


}
