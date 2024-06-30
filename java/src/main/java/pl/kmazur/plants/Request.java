package pl.kmazur.plants;

import java.time.Instant;

public class Request {
    private String process;
    private float requestedTokens;
    private long requestTimestamp;
    private int sleepPid;
    private double waitTime;

    public boolean isCompleted() {
        return process.endsWith("-completed");
    }

    public boolean isScan() {
        return process.endsWith("-scan");
    }

    public String getName() {
        return isCompleted() ? process.substring(0, process.indexOf("-completed")) : process;
    }

    // @formatter:off
    // Getters and Setters
    public String getProcess() { return process; }
    public void setProcess(String process) { this.process = process; }
    public int getRequestedTokens() { return (int) requestedTokens; }
    public void setRequestedTokens(double requestedTokens) { this.requestedTokens = (float) requestedTokens; }
    public double getRequestTimestamp() { return requestTimestamp; }
    public void setRequestTimestamp(double requestTimestamp) { this.requestTimestamp = (long) requestTimestamp; }
    public int getSleepPid() { return sleepPid; }
    public void setSleepPid(int sleepPid) { this.sleepPid = sleepPid; }
    public double getWaitTime() { return waitTime; }
    public void setWaitTime(double waitTime) { this.waitTime = waitTime; }
    // @formatter:on
}
