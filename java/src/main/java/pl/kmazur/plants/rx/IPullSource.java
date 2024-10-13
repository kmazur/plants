package pl.kmazur.plants.rx;

import java.util.function.Function;

@FunctionalInterface
public interface IPullSource<T> {
    T pull();

    default <K> IPullSource<K> map(final Function<T, K> mapper) {
        return () -> mapper.apply(this.pull());
    }

}
