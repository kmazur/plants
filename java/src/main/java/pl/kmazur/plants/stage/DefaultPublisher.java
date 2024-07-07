package pl.kmazur.plants.stage;

import org.reactivestreams.Publisher;
import org.reactivestreams.Subscriber;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

public class GetCpuTempPublisher implements Publisher<Float> {

    private List<Subscriber<? super Float>> subscribers = new ArrayList<>();
    private AtomicBoolean requested = new AtomicBoolean();
    private AtomicLong lastRequestMillis = new AtomicLong();

    @Override
    public void subscribe(Subscriber<? super Float> subscriber) {
        subscribers.add(subscriber);
        subscriber.onSubscribe(new CpuTempSubscription());
    }

    private class CpuTempSubscription implements org.reactivestreams.Subscription {
        @Override
        public void request(long n) {
            if (requested.compareAndSet(false, true)) {
                lastRequestMillis.set(System.currentTimeMillis());
            }
        }

        @Override
        public void cancel() {

        }
    }
}
