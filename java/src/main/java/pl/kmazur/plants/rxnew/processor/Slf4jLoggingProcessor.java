package pl.kmazur.plants.rxnew.processor;

import lombok.extern.slf4j.Slf4j;
import org.reactivestreams.Subscriber;
import org.reactivestreams.Subscription;
import org.slf4j.event.Level;

@Slf4j
public class Slf4jLoggingProcessor<T> extends AbstractFanOutProcessor<T, T> {

    private final String name;
    private final Level  level;

    public Slf4jLoggingProcessor(String name, Level level) {
        this.name  = name;
        this.level = level;
    }

    @Override
    public void subscribe(Subscriber<? super T> s) {
        log.atLevel(level).log("{} subscribe", name);
        super.subscribe(s);
    }

    @Override
    public void onSubscribe(Subscription s) {
        log.atLevel(level).log("{} onSubscribe", name);
        super.onSubscribe(s);
        this.subscription.get().request(1);
    }

    @Override
    public void onNext(T elem) {
        log.atLevel(level).log("{} onNext: {}", name, elem);
        publish(elem);
        this.subscription.get().request(1);
    }

    @Override
    public void onError(Throwable t) {
        log.atLevel(level).log("{} onError", name);
        super.onError(t);
    }

    @Override
    public void onComplete() {
        log.atLevel(level).log("{} onComplete", name);
        super.onComplete();
    }
}
