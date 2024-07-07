package pl.kmazur.plants.rx;

@FunctionalInterface
public interface ISource<T> {
    T get();
}
