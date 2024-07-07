package pl.kmazur.plants.rxnew.subscriber;

import org.reactivestreams.Subscription;

import java.util.function.Consumer;

public class AutoRequestSubscriber<T> extends DelegatingSubscriber<T> {

    private static final Consumer<Subscription> EMPTY_ON_SUBSCRIBE = s -> {};
    private static final Consumer<Throwable>    EMPTY_ON_ERROR     = t -> {};
    private static final Runnable               EMPTY_ON_COMPLETE  = () -> {};

    public static final long DEFAULT_REQUEST_COUNT = 1L;

    private final long requestCount;

    private Subscription subscription;

    public static <T> AutoRequestSubscriber<T> of(final Consumer<T> onNext) {
        return new AutoRequestSubscriber<>(EMPTY_ON_SUBSCRIBE, onNext, EMPTY_ON_ERROR, EMPTY_ON_COMPLETE);
    }

    public AutoRequestSubscriber(final Consumer<Subscription> onSubscribe, final Consumer<T> onNext, final Consumer<Throwable> onError, final Runnable onComplete) {
        this(DEFAULT_REQUEST_COUNT, onSubscribe, onNext, onError, onComplete);
    }

    public AutoRequestSubscriber(final long requestCount, final Consumer<Subscription> onSubscribe, final Consumer<T> onNext, final Consumer<Throwable> onError, final Runnable onComplete) {
        super(onSubscribe, onNext, onError, onComplete);
        this.requestCount = requestCount;
    }


    @Override
    public void onSubscribe(Subscription s) {
        super.onSubscribe(s);
        subscription = s;
        s.request(requestCount);
    }

    @Override
    public void onNext(T t) {
        super.onNext(t);
        subscription.request(requestCount);
    }

}