package pl.kmazur.plants;

import java.io.*;
import java.nio.file.*;
import java.time.Instant;
import java.util.*;
import java.util.stream.Collectors;

public class FileRequestSource implements RequestSource {
    private final String filePath;

    public FileRequestSource(String filePath) {
        this.filePath = filePath;
    }

    @Override
    public List<Request> getRequests() {
        try {
            return Files.lines(Paths.get(filePath))
                    .filter(line -> !line.isEmpty())
                    .map(this::parseLine)
                    .sorted(Comparator.comparingDouble(Request::getWaitTime).reversed())
                    .collect(Collectors.toList());
        } catch (IOException e) {
            e.printStackTrace();
            return Collections.emptyList();
        }
    }

    private Request parseLine(String line) {
        String[] parts = line.split("[=:]");
        String process = parts[0];
        double requestedTokens = Double.parseDouble(parts[1]);
        int sleepPid = Integer.parseInt(parts[2]);
        double requestTimestamp = UtilityFunctions.dateCompactToEpoch(parts[3]);
        double waitTime = Instant.now().getEpochSecond() - requestTimestamp;

        Request request = new Request();
        request.setProcess(process);
        request.setRequestedTokens(requestedTokens);
        request.setSleepPid(sleepPid);
        request.setRequestTimestamp(requestTimestamp);
        request.setWaitTime(waitTime);
        return request;
    }

    @Override
    public void markRequestFulfilled(Request request) {
        markRequestFulfilled(request.getProcess());
    }

    @Override
    public void markRequestFulfilled(String processName) {
        try {
            List<String> lines = Files.lines(Paths.get(filePath))
                    .filter(line -> !line.startsWith(processName + "="))
                    .collect(Collectors.toList());
            Files.write(Paths.get(filePath), lines);
        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}
