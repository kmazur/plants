package pl.kmazur.plants.rxnew;

import org.reactivestreams.Subscriber;
import org.reactivestreams.Subscription;

import java.util.function.Consumer;

public class DelegatingSubscriber<T> implements Subscriber<T> {
    private final Consumer<Subscription> onSubscribe;
    private final Consumer<T> onNext;
    private final Consumer<Throwable> onError;
    private final Runnable onComplete;

    public DelegatingSubscriber(
            Consumer<Subscription> onSubscribe,
            Consumer<T> onNext,
            Consumer<Throwable> onError,
            Runnable onComplete
    ) {
        this.onSubscribe = onSubscribe;
        this.onNext = onNext;
        this.onError = onError;
        this.onComplete = onComplete;
    }

    @Override
    public void onSubscribe(Subscription s) {
        onSubscribe.accept(s);
    }

    @Override
    public void onNext(T t) {
        onNext.accept(t);
    }

    @Override
    public void onError(Throwable t) {
        onError.accept(t);
    }

    @Override
    public void onComplete() {
        onComplete.run();
    }
}