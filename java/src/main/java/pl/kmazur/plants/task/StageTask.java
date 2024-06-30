package pl.kmazur.plants.task;

import lombok.extern.slf4j.Slf4j;
import pl.kmazur.plants.config.AppConfig;

@Slf4j
public abstract class StageTask extends AbstractTask {

    private final String inputDir;
    private final String outputDir;

    public StageTask(final AppConfig config) {

    }

}
