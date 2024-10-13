package pl.kmazur.plants.rx;

import java.util.ArrayList;
import java.util.List;
import java.util.function.Consumer;

public class PushSource<T> implements IPushSource<T> {

    private final List<Consumer<T>> consumers = new ArrayList<>();

    @Override
    public void subscribe(Consumer<T> consumer) {
        consumers.add(consumer);
    }

    public void produce(final T value) {
        for (final Consumer<T> c : consumers) {
            c.accept(value);
        }
    }

}
