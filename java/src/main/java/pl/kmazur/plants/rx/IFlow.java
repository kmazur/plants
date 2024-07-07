package pl.kmazur.plants.rx;

public interface IStage<T> {
    void accept(final T value);
}
