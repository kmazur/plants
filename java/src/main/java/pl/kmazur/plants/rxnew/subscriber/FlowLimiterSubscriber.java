package pl.kmazur.plants.rxnew.subscriber;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.reactivestreams.Subscriber;
import org.reactivestreams.Subscription;

import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

@Slf4j
public class FlowLimiterSubscriber<T> extends DelegatingSubscriber<T> implements IFlowLimiterSubscriber<T> {

    private ExternalControlSubscription subscription;

    private final AtomicLong    releases = new AtomicLong();
    private final AtomicBoolean opened   = new AtomicBoolean(true);

    public FlowLimiterSubscriber(final Subscriber<T> delegate) {
        super(delegate);
    }

    @Override
    public void onSubscribe(Subscription s) {
        subscription = new ExternalControlSubscription(s);
        super.onSubscribe(subscription);
    }

    @Override
    public void release(final long request) {
        if (!opened.get()) {
            releases.addAndGet(request);
            long decrement = release0();
            subscription.delegate.request(decrement);
        } else {
            subscription.delegate.request(1L);
        }
    }

    @Override
    public void closeFlow() {
        opened.set(false);
        releases.set(0L);
    }

    @Override
    public void openFlow() {
        opened.set(true);
        releases.set(0L);
    }

    private long release0() {
        if (opened.get()) {
            AtomicLong requested = subscription.requested;
            long       value;
            do {
                value = requested.get();
            } while (!requested.compareAndSet(value, 0));
            return value;
        }

        AtomicLong accumulator = subscription.requested;

        long decremented;
        long value;
        long changed;
        long request;
        do {
            request     = releases.get();
            value       = accumulator.get();
            changed     = Math.max(0, value - request);
            decremented = value - changed;
        } while (!accumulator.compareAndSet(value, changed));

        do {
            request = releases.get();
        } while (!releases.compareAndSet(request, request - decremented));

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