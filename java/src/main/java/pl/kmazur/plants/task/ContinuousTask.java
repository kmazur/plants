package pl.kmazur.plants.task;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

import java.io.IOException;
import java.util.concurrent.TimeUnit;

@Slf4j
@RequiredArgsConstructor
public class ContinuousTask implements IContinuousTask {

    private final ITask delegate;
    private final long runIntervalMillis;
    private volatile boolean shouldRun = true;

    public static ContinuousTask of(final ITask task, long interval, TimeUnit unit) {
        return new ContinuousTask(task, unit.toMillis(interval));
    }

    @Override
    public void run() {
        while (shouldRun) {
            delegate.run();
            try {
                Thread.sleep(runIntervalMillis);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
    }

    @Override
    public void close() {
        shouldRun = false;
    }
}
