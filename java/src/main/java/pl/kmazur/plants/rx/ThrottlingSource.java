package pl.kmazur.plants.rx;


import lombok.extern.slf4j.Slf4j;
import pl.kmazur.plants.time.ITimeProvider;

import java.util.concurrent.TimeUnit;
import java.util.function.Supplier;

@Slf4j
public class ThrottlingSource<T> implements IPullSource<T> {
    private final IPullSource<T> flow;
    private final ITimeProvider timeProvider;
    private final Supplier<T> throttledValue;
    private final long maxRatePerMillis;

    private long lastExecutionTime = 0;

    public ThrottlingSource(IPullSource<T> flow,
                            ITimeProvider timeProvider,
                            long maxRate, TimeUnit timeUnit,
                            Supplier<T> throttledValue) {
        this.flow = flow;
        this.timeProvider = timeProvider;
        this.throttledValue = throttledValue;
        this.maxRatePerMillis = timeUnit.toMillis(maxRate);
    }

    @Override
    public T pull() {
        long currentTime = timeProvider.getCurrentMillis();
        long elapsedTime = currentTime - lastExecutionTime;

        if (elapsedTime < maxRatePerMillis) {
            try {
                Thread.sleep(maxRatePerMillis - elapsedTime);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
        lastExecutionTime = timeProvider.getCurrentMillis();
        return flow.pull();
    }

}
