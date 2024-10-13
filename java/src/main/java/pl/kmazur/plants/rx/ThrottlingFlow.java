package pl.kmazur.plants.rx;


import pl.kmazur.plants.time.ITimeProvider;

import java.util.concurrent.TimeUnit;
import java.util.function.Supplier;

public class ThrottlingFlow<F, T> implements IFlow<F, T> {
    private final IFlow<F, T> flow;
    private final ITimeProvider timeProvider;
    private final Supplier<T> throttledValue;
    private final long maxRatePerMillis;

    private long lastExecutionTime = 0;

    public ThrottlingFlow(IFlow<F, T> flow,
                          ITimeProvider timeProvider,
                          long maxRate, TimeUnit timeUnit,
                          Supplier<T> throttledValue) {
        this.flow = flow;
        this.timeProvider = timeProvider;
        this.throttledValue = throttledValue;
        this.maxRatePerMillis = timeUnit.toMillis(maxRate);
    }

    @Override
    public T apply(F value) {
        long currentTime = timeProvider.getCurrentMillis();
        long elapsedTime = currentTime - lastExecutionTime;

        if (elapsedTime < maxRatePerMillis) {
            return throttledValue.get();
        }
        lastExecutionTime = currentTime;

        T result = flow.apply(value);
        return result;
    }
}
