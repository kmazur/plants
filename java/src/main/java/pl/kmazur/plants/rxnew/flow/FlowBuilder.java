package pl.kmazur.plants.rxnew.flow;

import lombok.extern.slf4j.Slf4j;
import org.reactivestreams.Processor;
import org.reactivestreams.Publisher;
import org.reactivestreams.Subscriber;

import java.util.Objects;

@Slf4j
public final class FlowBuilder<T> {
    private final Publisher<T> publisher;

    private FlowBuilder(final Publisher<T> publisher) {
        this.publisher = Objects.requireNonNull(publisher, "publisher");
    }

    public static <T> FlowBuilder<T> from(final Publisher<T> publisher) {
        return new FlowBuilder<>(publisher);
    }

    public <R, P extends Processor<T, R>> FlowBuilder<R> via(final P processor) {
        Objects.requireNonNull(processor, "processor");
        log.info("Connecting {} to processor {}", publisher, processor);

        publisher.subscribe(processor);
        return new FlowBuilder<>(processor);
    }

    public void to(final Subscriber<? super T> subscriber) {
        Objects.requireNonNull(subscriber, "subscriber");
        log.info("Connecting {} to subscriber {}", publisher, subscriber);

        publisher.subscribe(subscriber);
    }
}
