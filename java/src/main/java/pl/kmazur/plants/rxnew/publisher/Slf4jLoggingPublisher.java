package pl.kmazur.plants.rxnew.publisher;

import lombok.extern.slf4j.Slf4j;
import org.reactivestreams.Subscriber;
import org.slf4j.event.Level;

@Slf4j
public class Slf4jLoggingPublisher<T> implements IExternalSourcePublisher<T> {

    private final IExternalSourcePublisher<T> delegate;
    private final String                      name;
    private final Level                       level;

    public Slf4jLoggingPublisher(IExternalSourcePublisher<T> delegate, String name, Level level) {
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
    public void publish(T element) {
        log.atLevel(level).log("{} publish {}", name, element);
        delegate.publish(element);
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
