package pl.kmazur.plants;

import java.time.Instant;
import java.util.*;
import java.util.concurrent.*;

public class Scheduler {
    private final ConfigManager config;
    private final ConfigManager workUnitStatsConfig;
    private final RequestSource requestSource;

    private final Map<String, WorkUnit> workStats;
    private final Map<String, WorkUnit> runningProcesses;

    public Scheduler(ConfigManager config, ConfigManager workUnitStatsConfig, RequestSource requestSource) {
        this.config = config;
        this.workUnitStatsConfig = workUnitStatsConfig;
        this.requestSource = requestSource;
        this.workStats = new ConcurrentHashMap<>();
        this.runningProcesses = new ConcurrentHashMap<>();
        loadWorkUnits();
    }

    public void run() {
        while (true) {
            UtilityFunctions.log("Scheduler pass started");
            if (!isCpuTempCritical()) {
                config.loadConfig();
                runScheduler();
            } else {
                UtilityFunctions.log("Temperature critical");
                sleep(2 * (int) config.getRunInterval());
            }
            sleepForInterval();
        }
    }

    private void loadWorkUnits() {
        List<WorkUnit> workUnits = new ArrayList<>();//workUnitStatsConfig.loadAllWorkUnits();
        workUnits.forEach(workUnit -> workStats.put(workUnit.getName(), workUnit));
    }

    private void runScheduler() {
        List<Request> processedRequests = requestSource.getRequests();
        processCompletedRequests(processedRequests);
        processNormalRequests(processedRequests);
    }

    private void processNormalRequests(List<Request> processedRequests) {
        for (Request request : processedRequests) {
            if (!processRequest(request)) break;
        }
    }

    private void processCompletedRequests(List<Request> requests) {
        requests.removeIf(request -> {
            if (request.isCompleted()) {
                handleCompletedRequest(request);
                return true;
            }
            return false;
        });
    }

    private boolean isEvaluationRequired(Request request) {
        String name = request.getName();
        if (request.isScan() || !workStats.containsKey(name) || workStats.get(name).needsEvaluation(config.getReevaluationInterval())) {
            UtilityFunctions.log("Evaluation required for process: " + name);
            return true;
        }
        return false;
    }

    private boolean processRequest(Request request) {
        if (isEvaluationRequired(request)) {
            waitForAllProcessesToComplete();
            coolOff();
            performProcessLoadDiscovery(request);
            return false;
        }
        if (canRunProcess(request)) {
            runProcess(request);
            return true;
        }
        return true;
    }

    private boolean canRunProcess(Request request) {
        float estimatedTemp = getCpuTempEstimate();
        float maxTemp = config.getMaxTemp();
        WorkUnit workUnit = workStats.get(request.getProcess());

        double requestedTokens = request.getRequestedTokens();
        float estimatedCpuTempIncrease = (float) (Math.max(0.2f, workUnit.getCpuTempIncreasePerToken()) * requestedTokens);
        return estimatedTemp + estimatedCpuTempIncrease <= maxTemp;
    }

    private float getCpuTempEstimate() {
        float currentTemp = UtilityFunctions.getCpuTempFloat();
        float estimatedTempIncrease = 0.0f;
        long now = Instant.now().getEpochSecond();

        for (WorkUnit workUnit : runningProcesses.values()) {
            int requestedTokens = workUnit.getLastRequestedTokens();
            long startTime = workUnit.getStartTime();
            long elapsed = now - startTime;
            float estimatedTotalDuration = workUnit.getSecondsPerToken() * requestedTokens;
            float stillToGo = Math.max(0.0f, estimatedTotalDuration - elapsed);
            float multiplier = stillToGo / estimatedTotalDuration;

            float estimatedTotalCpuTempIncrease = workUnit.getCpuTempIncreasePerToken() * requestedTokens;
            float stillCpuToIncrease = multiplier * estimatedTotalCpuTempIncrease;
            estimatedTempIncrease += stillCpuToIncrease;
        }

        return currentTemp + estimatedTempIncrease;
    }

    private void handleCompletedRequest(Request request) {
        runningProcesses.remove(request.getName());
        requestSource.markRequestFulfilled(request);
        UtilityFunctions.wakeUpProcess(request);
    }

    private void runProcess(Request request) {
        String processName = request.getName();
        if (runningProcesses.containsKey(processName)) {
            UtilityFunctions.log("Process already running: " + processName);
            return;
        }
        UtilityFunctions.log("Running process: " + processName);

        WorkUnit workUnit = workStats.get(processName);
        runningProcesses.put(processName, workUnit);
        workUnit.startProcess(request.getRequestedTokens());
        requestSource.markRequestFulfilled(request);
        UtilityFunctions.wakeUpProcess(request);
    }

    private boolean waitForProcessToComplete(Request request, int waitInterval, boolean failFast) {
        long startTime = Instant.now().getEpochSecond();
        String name = request.getName();

        while (true) {
            sleep(waitInterval);
            List<Request> requests = requestSource.getRequests();
            if (isCpuTempCritical() && failFast) return true;

            long elapsed = Instant.now().getEpochSecond() - startTime;
            if (hasProcessCompleted(request, requests)) break;
            if (elapsed >= config.getProcessRunTimeout()) {
                UtilityFunctions.log("Timed out waiting for " + name + " to complete -> killing");
                killAndMarkProcess(name);
                return false;
            }
            UtilityFunctions.log(name + " still running: " + UtilityFunctions.vectorToString(UtilityFunctions.getKeys(runningProcesses)));
        }
        return false;
    }

    private boolean hasProcessCompleted(Request request, List<Request> requests) {
        return requests.stream().anyMatch(r -> r.getName().equals(request.getName()) && r.isCompleted());
    }

    private void performProcessLoadDiscovery(Request request) {
        String name = request.getName();
        if (!workStats.containsKey(name)) {
            UtilityFunctions.log("Found new work unit: " + name + " performing load evaluation");
            workStats.put(name, new WorkUnit(name));
        }

        WorkUnit workUnit = workStats.get(name);
        float initialTemp = UtilityFunctions.getCpuTempFloat();
        long startEpoch = Instant.now().getEpochSecond();
        UtilityFunctions.log(name + " -> initial cpu temp: " + initialTemp);

        runProcess(request);
        boolean prematureFinish = waitForProcessToComplete(request, 1, true);

        long endEpoch = Instant.now().getEpochSecond();
        float finalTemp = UtilityFunctions.getCpuTempFloat();
        float cpuIncrease = Math.max(0.0f, finalTemp - initialTemp);
        int duration = (int) (endEpoch - startEpoch);

        if (prematureFinish) {
            UtilityFunctions.log(name + " -> reached critical cpu temp during evaluation: " + finalTemp + ", increased: " + cpuIncrease + " elapsed: " + duration);
            waitForProcessToComplete(request, (int) config.getRunInterval(), false);
            duration = (int) (Instant.now().getEpochSecond() - startEpoch);
        } else {
            UtilityFunctions.log(name + " -> completed with cpu temp: " + finalTemp + ", increased: " + cpuIncrease + " took: " + duration + " sec");
        }

        workUnit.addEvaluation(request.getRequestedTokens(), duration, cpuIncrease, request.getSleepPid());
        UtilityFunctions.log(name + " updated stats: [secondsPerToken: " + workUnit.getSecondsPerToken() + ", tempPerToken: " + workUnit.getCpuTempIncreasePerToken());
        //workUnitStatsConfig.saveWorkUnit(workUnit);
    }

    private void coolOff() {
        float temp = UtilityFunctions.getCpuTempFloat();
        if (temp <= config.getMinTemp()) {
            UtilityFunctions.log("No need to cool off - currentTemp(" + temp + ") < " + config.getMinTemp());
        } else {
            UtilityFunctions.log("Cooling off for " + config.getCoolOffTime() + " seconds");
            sleep((int) config.getCoolOffTime());
        }
    }

    private void waitForAllProcessesToComplete() {
        UtilityFunctions.log("Wait for all processes to complete");
        long startTime = Instant.now().getEpochSecond();
        while (!runningProcesses.isEmpty()) {
            if (Instant.now().getEpochSecond() - startTime >= config.getProcessRunTimeout()) {
                UtilityFunctions.log("Timed out waiting for all processes to complete: " + UtilityFunctions.vectorToString(UtilityFunctions.getKeys(runningProcesses)));
                runningProcesses.keySet().forEach(this::killAndMarkProcess);
                break;
            }
            UtilityFunctions.log("Waiting for all processes to complete: " + UtilityFunctions.vectorToString(UtilityFunctions.getKeys(runningProcesses)));
            List<Request> requests = requestSource.getRequests();
            processCompletedRequests(requests);
            sleepForInterval();
        }
    }

    private void killAndMarkProcess(String name) {
        if (runningProcesses.containsKey(name)) {
            WorkUnit workUnit = runningProcesses.get(name);
            UtilityFunctions.killGroup(workUnit.getLastGroupId());
            requestSource.markRequestFulfilled(workUnit.getName());
            requestSource.markRequestFulfilled(workUnit.getName() + "-completed");
        }
    }

    private boolean isCpuTempCritical() {
        return UtilityFunctions.getCpuTempFloat() >= config.getMaxTemp();
    }

    private void sleep(int seconds) {
        try {
            Thread.sleep(seconds * 1000L);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    private void sleepForInterval() {
        sleep((int) config.getRunInterval());
    }
}
