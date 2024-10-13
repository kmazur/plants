package pl.kmazur.plants.rxnew.subscriber;

import lombok.extern.slf4j.Slf4j;
import org.reactivestreams.Subscriber;
import org.reactivestreams.Subscription;

@Slf4j
public class AutoRequestSubscriber<T> implements Subscriber<T> {

    public static final long DEFAULT_REQUEST_COUNT = 1L;

    private final long          requestCount;
    private final Subscriber<T> delegate;

    private Subscription subscription;

    public AutoRequestSubscriber(final Subscriber<T> delegate) {
        this(DEFAULT_REQUEST_COUNT, delegate);
    }

    public AutoRequestSubscriber(final long requestCount, final Subscriber<T> delegate) {
        this.delegate     = delegate;
        this.requestCount = requestCount;
    }

    @Override
    public void onSubscribe(Subscription s) {
        delegate.onSubscribe(s);
        subscription = s;
        s.request(requestCount);
    }

    @Override
    public void onNext(T t) {
        delegate.onNext(t);
        subscription.request(requestCount);
    }

    @Override
    public void onError(Throwable t) {
        delegate.onError(t);
    }

    @Override
    public void onComplete() {
        delegate.onComplete();
    }

}