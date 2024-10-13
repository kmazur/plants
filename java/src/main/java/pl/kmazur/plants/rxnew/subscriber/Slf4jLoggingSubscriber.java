package pl.kmazur.plants.rxnew.subscriber;

import lombok.extern.slf4j.Slf4j;
import org.reactivestreams.Subscriber;
import org.reactivestreams.Subscription;
import org.slf4j.event.Level;

@Slf4j
public class Slf4jLoggingSubscriber<T> extends DelegatingSubscriber<T> {

    private final Level  level;
    private final String name;

    public Slf4jLoggingSubscriber(final Subscriber<T> delegate) {
        this(delegate, Level.INFO);
    }

    public Slf4jLoggingSubscriber(final String name, final Subscriber<T> delegate) {
        this(name, delegate, Level.INFO);
    }

    public Slf4jLoggingSubscriber(final Subscriber<T> delegate, final Level level) {
        super(delegate);
        this.level = level;
        this.name  = this.getClass().getSimpleName();
    }

    public Slf4jLoggingSubscriber(final String name, final Subscriber<T> delegate, final Level level) {
        super(delegate);
        this.level = level;
        this.name  = name;
    }

    @Override
    public void onSubscribe(Subscription s) {
        log.atLevel(level).log("{} onSubscribe", name);
        super.onSubscribe(s);
    }

    @Override
    public void onNext(T element) {
        log.atLevel(level).log("{} onNext: {}", name, element);
        super.onNext(element);
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