package pl.kmazur.plants;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Instant;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public class UtilityFunctions {
    public static void log(String message) {
        System.out.println("[" + Instant.now() + "] INFO " + message);
    }

    public static void wakeUpProcess(Request request) {
        wakeUpProcess(request.getSleepPid());
    }

    public static void wakeUpProcess(int pid) {
        // Logic to wake up process
    }

    public static void killGroup(int pgid) {
        // Logic to kill process group
    }

    public static void ensureFileExists(String filePath) {
        Path path = Paths.get(filePath);
        if (Files.notExists(path)) {
            try {
                Files.createFile(path);
            } catch (IOException e) {
                e.printStackTrace();
            }
        }
    }

    public static float getCpuTempFloat() {
        // Logic to get CPU temperature
        return 0.0f;
    }

    public static long dateCompactToEpoch(String inputDate) {
        DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss");
        return Instant.from(formatter.parse(inputDate)).getEpochSecond();
    }

    public static String vectorToString(List<String> vec) {
        return String.join(", ", vec);
    }

    public static <T> List<String> getKeys(Map<String, T> map) {
        return new ArrayList<>(map.keySet());
    }
}
