package pl.kmazur.plants.rxnew.processor;

import org.reactivestreams.Processor;
import org.reactivestreams.Subscriber;
import org.reactivestreams.Subscription;
import pl.kmazur.plants.rxnew.publisher.FanOutPublisher;

import java.util.concurrent.atomic.AtomicReference;

public class AbstractProcessor<T, R> implements Processor<T, R> {

    private final AtomicReference<Subscription> subscription = new AtomicReference<>();
    private final FanOutPublisher<R>            publisher    = new FanOutPublisher<>();

    private boolean completed = false;

    @Override
    public void subscribe(Subscriber<? super R> subscriber) {
        publisher.subscribe(subscriber);
    }

    @Override
    public void onSubscribe(Subscription s) {
        if (subscription.compareAndSet(null, s)) {
            s.request(1);
        } else {
            throw new IllegalStateException("Only single onSubscribe should be called");
        }
    }

    @Override
    public void onNext(T item) {
        publisher.publish(item);
        subscription.get().request(1);
    }

    @Override
    public void onError(Throwable t) {
        completed = true;
        publisher.emitException(t);
    }

    @Override
    public void onComplete() {
        if (!completed) {
            completed = true;
            publisher.complete();
        }
    }

}