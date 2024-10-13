package pl.kmazur.plants.rxnew.publisher;

import lombok.extern.slf4j.Slf4j;
import org.reactivestreams.Subscriber;
import org.slf4j.event.Level;

@Slf4j
public class Slf4jOnDemandLoggingPublisher<T> implements IOnDemandPublisher<T> {

    private final IOnDemandPublisher<T> delegate;
    private final String                name;
    private final Level                 level;

    public Slf4jOnDemandLoggingPublisher(IOnDemandPublisher<T> delegate, String name) {
        this(delegate, name, Level.INFO);
    }

    public Slf4jOnDemandLoggingPublisher(IOnDemandPublisher<T> delegate, String name, Level level) {
        this.delegate = delegate;
        this.name     = name;
        this.level    = level;
    }

    @Override
    public void subscribe(Subscriber<? super T> s) {
        log.atLevel(level).log("{} subscribe", name);
        delegate.subscribe(s);
    }

    @Override
    public void publish() {
        log.atLevel(level).log("{} publish", name);
        delegate.publish();
    }

    @Override
    public void emitException(Throwable t) {
        log.atLevel(level).log("{} exception", name, t);
        delegate.emitException(t);
    }

    @Override
    public void complete() {
        log.atLevel(level).log("{} complete", name);
        delegate.complete();
    }

}
