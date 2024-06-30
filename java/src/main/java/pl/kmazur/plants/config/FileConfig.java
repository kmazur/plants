package pl.kmazur.plants.config;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.util.HashMap;
import java.util.Map;

public class FileConfig implements TypedConfig {

    private final String configFilePath;
    private final Map<String, String> map;

    public FileConfig(String configFilePath) {
        this.configFilePath = configFilePath;
        this.map = new HashMap<>();
    }

    @Override
    public String get(String key) {
        return map.get(key);
    }

    @Override
    public void set(String key, String value) {
        map.put(key, value);
    }

    public void readConfigFile() {
        map.clear();
        try (BufferedReader reader = Files.newBufferedReader(Paths.get(configFilePath))) {
            reader.lines()
                    .map(line -> line.split("="))
                    .filter(parts -> parts.length == 2)
                    .forEach(parts -> map.put(parts[0], parts[1]));
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    public void writeConfigFile() {
        Path path = Paths.get(configFilePath);
        try (FileChannel channel = FileChannel.open(path, StandardOpenOption.WRITE, StandardOpenOption.CREATE);
             FileLock lock = channel.lock();
             BufferedWriter writer = Files.newBufferedWriter(path)
        ) {
            for (Map.Entry<String, String> entry : map.entrySet()) {
                writer.write(entry.getKey() + "=" + entry.getValue());
                writer.newLine();
            }

        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

}
