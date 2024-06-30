package pl.kmazur.plants;

public class Evaluation {
    private final int requestedTokens;
    private final int durationSeconds;
    private final float cpuTempIncrease;

    public Evaluation(int requestedTokens, int durationSeconds, float cpuTempIncrease) {
        this.requestedTokens = requestedTokens;
        this.durationSeconds = durationSeconds;
        this.cpuTempIncrease = cpuTempIncrease;
    }

    public int getRequestedTokens() {
        return requestedTokens;
    }

    public int getDurationSeconds() {
        return durationSeconds;
    }

    public float getCpuTempIncrease() {
        return cpuTempIncrease;
    }

    public String serialize() {
        return requestedTokens + "," + durationSeconds + "," + cpuTempIncrease;
    }

    public static Evaluation deserialize(String data) {
        String[] parts = data.split(",");
        return new Evaluation(Integer.parseInt(parts[0]), Integer.parseInt(parts[1]), Float.parseFloat(parts[2]));
    }
}
