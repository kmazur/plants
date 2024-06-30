package pl.kmazur.plants.config;

import java.util.concurrent.TimeUnit;

public class AppConfig implements TypedConfig {

    private final FileConfig config;

    private float minTemp;
    private float maxTemp;
    private float runInterval;
    private float reevaluationInterval;
    private float coolOffTime;
    private int requiredEvaluationCount;
    private float processRunTimeout;

    public AppConfig(FileConfig config) {
        this.config = config;
        loadConfig();
    }

    private void loadConfig() {
        this.config.readConfigFile();
        minTemp = config.getOrSetFloat("orchestrator.min_temperature", 60f);
        maxTemp = config.getOrSetFloat("orchestrator.max_temperature", 79f);
        runInterval = config.getOrSetFloat("orchestrator.run_interval", 2f);
        reevaluationInterval = config.getOrSetFloat("orchestrator.reevaluation_interval", TimeUnit.HOURS.toSeconds(6));
        coolOffTime = config.getOrSetFloat("orchestrator.cool_off_seconds", 60);
        requiredEvaluationCount = config.getOrSetInt("orchestrator.required_evaluation_count", 3);
        processRunTimeout = config.getOrSetFloat("orchestrator.process_run_timeout", TimeUnit.MINUTES.toSeconds(5));
    }

    // @formatter:off
    public float getMinTemp() { return minTemp; }
    public float getMaxTemp() { return maxTemp; }
    public float getRunInterval() { return runInterval; }
    public float getReevaluationInterval() { return reevaluationInterval; }
    public float getCoolOffTime() { return coolOffTime; }
    public float getRequiredEvaluationCount() { return requiredEvaluationCount; }
    public float getProcessRunTimeout() { return processRunTimeout; }@Override
    // @formatter:on

    public String get(String key) {
        return config.get(key);
    }

    @Override
    public void set(String key, String value) {
        config.set(key, value);
    }

    public String getTaskRootDir() {
        return "/home/user/WORK/tmp/pipeline";
    }
}
