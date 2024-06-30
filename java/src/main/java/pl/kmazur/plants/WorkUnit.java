package pl.kmazur.plants;

import java.time.Instant;
import java.util.*;
import java.util.stream.Collectors;

public class WorkUnit {
    private final String name;
    private long lastEvaluationEpoch;
    private int lastGroupId;
    private long startTime;
    private int lastRequestedTokens;
    private float cpuTempIncreasePerToken;
    private float secondsPerToken;

    private final Deque<Evaluation> evaluations;

    public WorkUnit(String name) {
        this.name = name;
        this.lastEvaluationEpoch = 0;
        this.lastGroupId = 0;
        this.cpuTempIncreasePerToken = 0.0f;
        this.secondsPerToken = 1.0f;
        this.startTime = 0;
        this.lastRequestedTokens = 0;
        this.evaluations = new ArrayDeque<>();
    }

    public String getName() {
        return name;
    }

    public int getLastGroupId() {
        return lastGroupId;
    }

    public void startProcess(int requestedTokens) {
        this.startTime = Instant.now().getEpochSecond();
        this.lastRequestedTokens = requestedTokens;
    }

    public long getStartTime() {
        return startTime;
    }

    public int getLastRequestedTokens() {
        return lastRequestedTokens;
    }

    public float getCpuTempIncreasePerToken() {
        return cpuTempIncreasePerToken;
    }

    public float getSecondsPerToken() {
        return secondsPerToken;
    }

    public void addEvaluation(int requestedTokens, int durationSeconds, float cpuTempIncrease, int pgid) {
        if (evaluations.size() == 10) {
            evaluations.removeFirst();
        }
        evaluations.addLast(new Evaluation(requestedTokens, durationSeconds, cpuTempIncrease));
        lastEvaluationEpoch = Instant.now().getEpochSecond();
        lastGroupId = pgid;
        calculate();
    }

    public boolean needsEvaluation(float reevaluationInterval) {
        return evaluations.size() < 3 || Instant.now().getEpochSecond() - lastEvaluationEpoch > reevaluationInterval;
    }

    private void calculate() {
        int totalTokensRequested = evaluations.stream().mapToInt(Evaluation::getRequestedTokens).sum();
        float totalCpuIncreased = (float) evaluations.stream().mapToDouble(Evaluation::getCpuTempIncrease).sum();
        float totalDuration = (float) evaluations.stream().mapToDouble(Evaluation::getDurationSeconds).sum();

        cpuTempIncreasePerToken = totalCpuIncreased / totalTokensRequested;
        secondsPerToken = totalDuration / totalTokensRequested;
    }

    public String serialize() {
        return name + ";" +
                lastEvaluationEpoch + ";" +
                lastGroupId + ";" +
                startTime + ";" +
                lastRequestedTokens + ";" +
                cpuTempIncreasePerToken + ";" +
                secondsPerToken + ";" +
                evaluations.stream()
                        .map(Evaluation::serialize)
                        .collect(Collectors.joining("|"));
    }

    public static WorkUnit deserialize(String data) {
        String[] parts = data.split(";");
        WorkUnit workUnit = new WorkUnit(parts[0]);

        workUnit.lastEvaluationEpoch = Long.parseLong(parts[1]);
        workUnit.lastGroupId = Integer.parseInt(parts[2]);
        workUnit.startTime = Long.parseLong(parts[3]);
        workUnit.lastRequestedTokens = Integer.parseInt(parts[4]);
        workUnit.cpuTempIncreasePerToken = Float.parseFloat(parts[5]);
        workUnit.secondsPerToken = Float.parseFloat(parts[6]);

        String[] evals = parts[7].split("\\|");
        for (String eval : evals) {
            workUnit.evaluations.addLast(Evaluation.deserialize(eval));
        }

        return workUnit;
    }
}
