package pl.kmazur.plants.camera;

import lombok.extern.slf4j.Slf4j;

import java.io.IOException;

@Slf4j
public class Camera {

    public void captureImage(String imageConfigFile, String imageCapturePath) {
        ProcessBuilder processBuilder = new ProcessBuilder();
        processBuilder.command("bash", "-c", "libcamera-still -c " + imageConfigFile + " -o " + imageCapturePath + " -n -t 1");

        try {
            Process process = processBuilder.start();
            int exitCode = process.waitFor();
            if (exitCode != 0) {
                log.error("Error occurred while capturing image. Exit code: " + exitCode);
            }
        } catch (IOException | InterruptedException e) {
            log.error("Error during image capture", e);
        }
    }

}