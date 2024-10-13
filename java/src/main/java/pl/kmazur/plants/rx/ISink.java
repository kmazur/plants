package pl.kmazur.plants.rx;

@FunctionalInterface
public interface ISink<T> {
    void accept(final T value);
}
