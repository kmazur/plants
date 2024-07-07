package pl.kmazur.plants.rx;

import pl.kmazur.plants.time.ITimeProvider;

import java.util.concurrent.TimeUnit;
import java.util.function.Function;
import java.util.function.Supplier;

@FunctionalInterface
public interface ISource<T> {
    T pull();

    default <K> ISource<K> map(final Function<T, K> mapper) {
        return () -> mapper.apply(this.pull());
    }

    default ISource<T> throttle(final ITimeProvider provider, final int maxRate, final TimeUnit timeUnit, Supplier<T> throttledValue) {
        return new ThrottlingSource<>(this, provider, maxRate, timeUnit, throttledValue);
    }
}
