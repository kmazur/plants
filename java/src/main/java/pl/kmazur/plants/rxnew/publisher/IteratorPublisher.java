package pl.kmazur.plants.rxnew.publisher;

import org.reactivestreams.Publisher;
import org.reactivestreams.Subscriber;
import org.reactivestreams.Subscription;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Queue;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

public class IteratorPublisher<T> implements Publisher<T> {
    private final List<SubscriberWrapper> subscribers = new ArrayList<>();
    private final Iterator<T>             iterator;
    private       boolean                 completed   = false;

    public IteratorPublisher(final Iterator<T> iterator) {
        this.iterator = iterator;
    }

    @Override
    public void subscribe(Subscriber<? super T> subscriber) {
        if (!subscribers.isEmpty()) {
            throw new IllegalStateException("Only one subscriber allowed");
        }
        SubscriberWrapper wrapper = new SubscriberWrapper(subscriber);
        subscribers.add(wrapper);
        subscriber.onSubscribe(wrapper.subscription);
    }

    private void emitComplete() {
        for (SubscriberWrapper wrapper : subscribers) {
            wrapper.subscriber.onComplete();
        }
        subscribers.clear();
    }

    private class SubscriberWrapper {
        final Subscriber<? super T> subscriber;
        final SubscriptionImpl      subscription;
        final AtomicLong            requested      = new AtomicLong();
        final AtomicBoolean         canceled       = new AtomicBoolean(false);
        final Queue<T>              personalBuffer = new ConcurrentLinkedQueue<>();

        SubscriberWrapper(Subscriber<? super T> subscriber) {
            this.subscriber   = subscriber;
            this.subscription = new SubscriptionImpl();
        }

        void emit() {
            while (requested.get() > 0 && !iterator.hasNext() && !canceled.get()) {
                T element = iterator.next();
                if (element != null) {
                    subscriber.onNext(element);
                    requested.decrementAndGet();
                }
            }

            if (!iterator.hasNext()) {
                completed = true;
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
                subscribers.remove(IteratorPublisher.SubscriberWrapper.this);
            }
        }
    }
}