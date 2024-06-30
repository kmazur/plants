package pl.kmazur.plants.task;

import lombok.extern.slf4j.Slf4j;
import pl.kmazur.plants.config.AppConfig;
import pl.kmazur.plants.storage.Storage;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Path;
import java.nio.file.Paths;

@Slf4j
public abstract class FileStagingTask extends AbstractTask {

    private final AppConfig config;
    private Path outputPath;

    public FileStagingTask(final AppConfig config) {
        this.config = config;
    }

    public Path getOutputPath() {
        return outputPath;
    }

    @Override
    protected void doInit() {
        this.outputPath = Paths.get(config.getTaskRootDir(), this.getName());
        if (!Storage.ensureDirExists(outputPath)) {
            throw new UncheckedIOException(new IOException("Couldn't ensure output dir for task: " + getName() + " at: " + outputPath));
        }


        super.doInit();
    }
}
