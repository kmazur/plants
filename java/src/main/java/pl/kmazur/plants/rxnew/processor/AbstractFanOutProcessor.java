package pl.kmazur.plants.rxnew.processor;

import org.reactivestreams.Processor;
import org.reactivestreams.Subscription;
import pl.kmazur.plants.rxnew.publisher.FanOutPublisher;

import java.util.concurrent.atomic.AtomicReference;

public abstract class AbstractFanOutProcessor<T, R> extends FanOutPublisher<R> implements Processor<T, R> {

    protected final AtomicReference<Subscription> subscription = new AtomicReference<>();

    @Override
    public void onSubscribe(Subscription s) {
        if (!subscription.compareAndSet(null, s)) {
            throw new IllegalStateException("Only single onSubscribe should be called");
        }
    }

    @Override
    public void onError(Throwable t) {
        emitException(t);
    }

    @Override
    public void onComplete() {
        complete();
    }
}