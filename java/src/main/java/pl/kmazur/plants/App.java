package pl.kmazur.plants;

import pl.kmazur.plants.config.AppConfig;
import pl.kmazur.plants.config.FileConfig;
import pl.kmazur.plants.task.ContinuousTask;
import pl.kmazur.plants.task.ITask;
import pl.kmazur.plants.task.RecordVideoTask;
import pl.kmazur.plants.time.ITimeProvider;
import pl.kmazur.plants.time.SystemTimeProvider;

import java.util.concurrent.TimeUnit;

public class App {
    public static void main(String[] args) {
        FileConfig fileConfig = new FileConfig("C:/WORK/config.txt");

        AppConfig config = new AppConfig(fileConfig);
        ITimeProvider timeProvider = new SystemTimeProvider();
        RecordVideoTask task = new RecordVideoTask(config, timeProvider);
        task.init();
        task.run();

        try {
            ContinuousTask.of(new RecordVideoTask(config, timeProvider), 1, TimeUnit.SECONDS);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }
}
