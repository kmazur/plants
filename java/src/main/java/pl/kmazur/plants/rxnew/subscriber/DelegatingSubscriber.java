package pl.kmazur.plants.rxnew.subscriber;

import lombok.extern.slf4j.Slf4j;
import org.reactivestreams.Subscriber;
import org.reactivestreams.Subscription;

import java.util.Objects;
import java.util.function.Consumer;

@Slf4j
public class DelegatingSubscriber<T> implements Subscriber<T> {

    private static final Consumer<Subscription> EMPTY_ON_SUBSCRIBE = s -> {};
    private static final Consumer<Throwable>    EMPTY_ON_ERROR     = t -> {};
    private static final Runnable               EMPTY_ON_COMPLETE  = () -> {};

    protected final Consumer<Subscription> onSubscribe;
    protected final Consumer<T>            onNext;
    protected final Consumer<Throwable>    onError;
    protected final Runnable               onComplete;


    public static <T> DelegatingSubscriber<T> of(final Consumer<T> onNext) {
        return new DelegatingSubscriber<>(EMPTY_ON_SUBSCRIBE, onNext, EMPTY_ON_ERROR, EMPTY_ON_COMPLETE);
    }

    public DelegatingSubscriber(
            final Subscriber<T> subscriber
    ) {
        Objects.requireNonNull(subscriber, "subscriber");
        this.onSubscribe = subscriber::onSubscribe;
        this.onNext      = subscriber::onNext;
        this.onError     = subscriber::onError;
        this.onComplete  = subscriber::onComplete;
    }

    public DelegatingSubscriber(
            final Consumer<Subscription> onSubscribe,
            final Consumer<T> onNext,
            final Consumer<Throwable> onError,
            final Runnable onComplete
    ) {
        this.onSubscribe = Objects.requireNonNull(onSubscribe, "onSubscribe");
        this.onNext      = Objects.requireNonNull(onNext, "onNext");
        this.onError     = Objects.requireNonNull(onError, "onError");
        this.onComplete  = Objects.requireNonNull(onComplete, "onComplete");
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