package pl.kmazur.plants.rxnew;

import org.reactivestreams.Publisher;
import org.reactivestreams.Subscriber;
import org.reactivestreams.Subscription;

import java.util.ArrayList;
import java.util.List;
import java.util.Queue;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

public class FanOutPublisher<T> implements Publisher<T> {
    private final List<SubscriberWrapper> subscribers = new ArrayList<>();
    private boolean completed = false;

    @Override
    public void subscribe(Subscriber<? super T> subscriber) {
        SubscriberWrapper wrapper = new SubscriberWrapper(subscriber);
        subscribers.add(wrapper);
        subscriber.onSubscribe(wrapper.subscription);
    }

    public void publish(T element) {
        for (SubscriberWrapper wrapper : subscribers) {
            wrapper.personalBuffer.add(element);
        }
        emitElements();
    }

    public void emitException(final Exception t) {
        completed = true;
        for (SubscriberWrapper wrapper : subscribers) {
            wrapper.subscriber.onError(t);
        }
        emitElements();
    }

    public void complete() {
        completed = true;
        emitElements();
    }

    private void emitElements() {
        for (SubscriberWrapper wrapper : subscribers) {
            wrapper.emit();
        }

        if (completed) {
            for (SubscriberWrapper wrapper : subscribers) {
                wrapper.subscriber.onComplete();
            }
            subscribers.clear();
        }
    }

    private class SubscriberWrapper {
        final Subscriber<? super T> subscriber;
        final SubscriptionImpl subscription;
        final AtomicLong requested = new AtomicLong();
        final AtomicBoolean canceled = new AtomicBoolean(false);
        final Queue<T> personalBuffer = new ConcurrentLinkedQueue<>();

        SubscriberWrapper(Subscriber<? super T> subscriber) {
            this.subscriber = subscriber;
            this.subscription = new SubscriptionImpl();
        }

        void emit() {
            while (requested.get() > 0 && !personalBuffer.isEmpty() && !canceled.get()) {
                T element = personalBuffer.poll();
                if (element != null) {
                    subscriber.onNext(element);
                    requested.decrementAndGet();
                }
            }

            if (completed) {
                subscriber.onComplete();
            }
        }

        private class SubscriptionImpl implements Subscription {
            @Override
            public void request(long n) {
                if (canceled.get()) {
                    return;
                }
                if (n <= 0) {
                    subscriber.onError(new IllegalArgumentException("Requested number of items must be positive"));
                    return;
                }
                requested.addAndGet(n);
                emit();
            }

            @Override
            public void cancel() {
                canceled.set(true);
                requested.set(0);
                subscribers.remove(SubscriberWrapper.this);
            }
        }
    }
}