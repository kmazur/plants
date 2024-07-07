package pl.kmazur.plants.rxnew.subscriber;

import org.reactivestreams.Subscription;

import java.util.function.Consumer;

public class RequestOneSubscriber<T> extends DelegatingSubscriber<T> {

    private Subscription subscription;

    public RequestOneSubscriber(
            Consumer<Subscription> onSubscribe,
            Consumer<T> onNext,
            Consumer<Throwable> onError,
            Runnable onComplete
    ) {
        super(onSubscribe, onNext, onError, onComplete);
    }

    @Override
    public void onSubscribe(Subscription s) {
        super.onSubscribe(s);
        subscription = s;
        s.request(1);
    }

    @Override
    public void onNext(T t) {
        super.onNext(t);
        subscription.request(1);
    }

}