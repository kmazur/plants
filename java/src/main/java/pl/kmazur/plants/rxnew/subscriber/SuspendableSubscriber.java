package pl.kmazur.plants.rxnew.subscriber;

import org.reactivestreams.Subscriber;
import org.reactivestreams.Subscription;

import java.util.Queue;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.atomic.AtomicBoolean;

public class SuspendableSubscriber<T> extends DelegatingSubscriber<T> implements ISuspendableSubscriber<T> {

    private final AtomicBoolean suspended = new AtomicBoolean();

    private final Queue<Runnable> queue = new ConcurrentLinkedQueue<>();

    public SuspendableSubscriber(Subscriber<T> subscriber) {
        super(subscriber);
    }

    @Override
    public void onSubscribe(Subscription s) {
        if (suspended.get()) {
            queue.offer(() -> super.onSubscribe(s));
        } else {
            super.onSubscribe(s);
        }
    }

    @Override
    public void onNext(T t) {
        if (suspended.get()) {
            queue.offer(() -> super.onNext(t));
        } else {
            super.onNext(t);
        }
    }

    @Override
    public void onError(Throwable t) {
        if (suspended.get()) {
            queue.offer(() -> super.onError(t));
        } else {
            super.onError(t);
        }
    }

    @Override
    public void onComplete() {
        if (suspended.get()) {
            queue.offer(super::onComplete);
        } else {
            super.onComplete();
        }
    }

    @Override
    public void suspend() {
        suspended.set(true);
    }

    @Override
    public void resume() {
        suspended.set(false);
        while (!queue.isEmpty()) {
            Runnable action = queue.poll();
            action.run();
        }
    }
}
