package pl.kmazur.plants;

import java.io.*;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.file.*;
import java.util.*;

import static pl.kmazur.plants.UtilityFunctions.ensureFileExists;

public class ConfigManager {
    private final String configFilePath;
    private final Map<String, String> configValues;

    private float minTemp;
    private float maxTemp;
    private float runInterval;
    private float reevaluationInterval;
    private float coolOffTime;
    private float requiredEvaluationCount;
    private float processRunTimeout;

    public ConfigManager(String configFilePath) {
        this.configFilePath = configFilePath;
        this.configValues = new HashMap<>();
        ensureFileExists(configFilePath);
        loadConfig();
    }

    public void loadConfig() {
        readConfigFile();
        minTemp = getOrSetConfig("orchestrator.min_temperature", 60f);
        maxTemp = getOrSetConfig("orchestrator.max_temperature", 80f);
        runInterval = getOrSetConfig("orchestrator.run_interval", 5f);
        reevaluationInterval = getOrSetConfig("orchestrator.reevaluation_interval", 1800f);
        coolOffTime = getOrSetConfig("orchestrator.cool_off_seconds", 60f);
        requiredEvaluationCount = getOrSetConfig("orchestrator.required_evaluation_count", 3f);
        processRunTimeout = getOrSetConfig("orchestrator.process_run_timeout", 1800f);
    }

    public String getOrSetConfig(String key, String defaultValue) {
        return configValues.computeIfAbsent(key, k -> {
            setConfig(key, defaultValue);
            return defaultValue;
        });
    }

    public float getOrSetConfig(String key, float defaultValue) {
        return Float.parseFloat(getOrSetConfig(key, Float.toString(defaultValue)));
    }

    public void setConfig(String key, String value) {
        configValues.put(key, value);
        writeConfigFile();
    }

    private void readConfigFile() {
        try (BufferedReader reader = Files.newBufferedReader(Paths.get(configFilePath))) {
            reader.lines()
                    .map(line -> line.split("="))
                    .filter(parts -> parts.length == 2)
                    .forEach(parts -> configValues.put(parts[0], parts[1]));
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    private void writeConfigFile() {
        try (RandomAccessFile file = new RandomAccessFile("/tmp/testfile.txt", "rw");
             FileChannel channel = file.getChannel();
             FileLock lock = channel.lock()) {
            // write to the channel
        } catch (IOException e) {
            e.printStackTrace();
        }

        try (FileChannel channel = FileChannel.open(Paths.get(configFilePath), StandardOpenOption.WRITE, StandardOpenOption.CREATE);
             FileLock lock = channel.lock();
             BufferedWriter writer = Files.newBufferedWriter(Paths.get(configFilePath))) {

            for (Map.Entry<String, String> entry : configValues.entrySet()) {
                writer.write(entry.getKey() + "=" + entry.getValue());
                writer.newLine();
            }

        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    public float getMinTemp() { return minTemp; }
    public float getMaxTemp() { return maxTemp; }
    public float getRunInterval() { return runInterval; }
    public float getReevaluationInterval() { return reevaluationInterval; }
    public float getCoolOffTime() { return coolOffTime; }
    public float getRequiredEvaluationCount() { return requiredEvaluationCount; }
    public float getProcessRunTimeout() { return processRunTimeout; }

    // Methods to save and load WorkUnit objects omitted for brevity
}
