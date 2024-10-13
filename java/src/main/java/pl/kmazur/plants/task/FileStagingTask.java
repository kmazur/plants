package pl.kmazur.plants.task;

import lombok.Getter;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import pl.kmazur.plants.config.AppConfig;
import pl.kmazur.plants.date.Constants;
import pl.kmazur.plants.storage.Storage;
import pl.kmazur.plants.time.ITimeProvider;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Path;
import java.nio.file.Paths;

@Slf4j
@RequiredArgsConstructor
public abstract class FileStagingTask extends AbstractTask {

    private final AppConfig config;
    private final ITimeProvider timeProvider;

    @Getter
    private Path outputPath;

    @Override
    protected void doInit() {
        this.outputPath = Paths.get(config.getTaskRootDir(), this.getName());
        if (!Storage.ensureDirExists(outputPath)) {
            throw new UncheckedIOException(new IOException("Couldn't ensure output dir for task: " + getName() + " at: " + outputPath));
        }

        super.doInit();
    }

    protected String getTimestampedFilePath(final String prefix, final String extension) {
        String dateTimeStr = timeProvider.getCurrentLocalDateTime().format(Constants.FORMATTER);
        String fileName = prefix + "_" + dateTimeStr + "." + extension;
        Path fullPath = outputPath.resolve(fileName);
        return fullPath.toString();
    }
}
