package pl.kmazur.plants.rx;

public interface PushSource<T> extends ISource<T> {
    void produce(final T value);
}
