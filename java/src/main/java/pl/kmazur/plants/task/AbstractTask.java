package pl.kmazur.plants.task;

import lombok.extern.slf4j.Slf4j;

@Slf4j
public abstract class AbstractTask implements Task, InitializingAware {

    @Override
    public final void init() {
        try {
            log.info("Initializing {}", getName());
            doInit();
        } catch (Exception e) {
            log.error("Error during initialization of {}", getName());
        } finally {
            log.info("Finished during initialization of {}", getName());
        }
    }

    protected void doInit() {
        // empty by default
    }

    @Override
    public final void run() {
        try {
            log.info("Starting task: {}", this.getName());
            doRun();
        } catch (Exception e) {
            log.warn("Exception during run {}", this.getName(), e);
        } finally {
            log.info("Completed task: {}", this.getName());
        }
    }

    protected abstract void doRun();
}
