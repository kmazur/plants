package pl.kmazur.plants.rxnew.subscriber;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.reactivestreams.Subscriber;
import org.reactivestreams.Subscription;

import java.util.concurrent.atomic.AtomicLong;

@Slf4j
public class ExternalSubscriber<T> extends DelegatingSubscriber<T> implements IExternalSubscriber<T> {

    private ExternalControlSubscription subscription;

    private final AtomicLong releaseRequest = new AtomicLong();

    public ExternalSubscriber(final Subscriber<T> delegate) {
        super(delegate);
    }

    @Override
    public void onSubscribe(Subscription s) {
        subscription = new ExternalControlSubscription(s);
        super.onSubscribe(subscription);
    }

    @Override
    public void release(final long request) {
        releaseRequest.addAndGet(request);
        long decrement = release0();
        subscription.delegate.request(decrement);
    }

    private long release0() {
        AtomicLong accumulator = subscription.requested;

        long decremented;
        long value;
        long changed;
        long request;
        do {
            request     = releaseRequest.get();
            value       = accumulator.get();
            changed     = Math.max(0, value - request);
            decremented = value - changed;
        } while (!accumulator.compareAndSet(value, changed));

        do {
            request = releaseRequest.get();
        } while (!releaseRequest.compareAndSet(request, request - decremented));

        return decremented;
    }

    @RequiredArgsConstructor
    private class ExternalControlSubscription implements Subscription {

        private final Subscription delegate;
        private final AtomicLong   requested = new AtomicLong();

        @Override
        public void request(long n) {
            requested.addAndGet(n);
            long decrement = release0();
            if (decrement > 0) {
                subscription.delegate.request(decrement);
            }
        }

        @Override
        public void cancel() {
            delegate.cancel();
        }
    }
}