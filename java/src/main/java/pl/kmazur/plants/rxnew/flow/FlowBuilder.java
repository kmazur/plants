package pl.kmazur.plants.rxnew.flow;

import org.reactivestreams.Processor;
import org.reactivestreams.Publisher;
import org.reactivestreams.Subscriber;

public class StreamBuilder<T> {
    private final Publisher<T> publisher;

    private StreamBuilder(final Publisher<T> publisher) {
        this.publisher = publisher;
    }

    public static <T> StreamBuilder<T> from(final Publisher<T> publisher) {
        return new StreamBuilder<>(publisher);
    }

    public <R> StreamBuilder<R> via(final Processor<T, R> processor) {
        publisher.subscribe(processor);
        return new StreamBuilder<>(processor);
    }

    public void to(final Subscriber<? super T> subscriber) {
        publisher.subscribe(subscriber);
    }
}
