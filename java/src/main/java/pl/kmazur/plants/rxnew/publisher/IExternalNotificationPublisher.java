package pl.kmazur.plants.rxnew.publisher;

import org.reactivestreams.Publisher;

public interface IExternalSourcePublisher<T> extends Publisher<T> {

    void publish(final T element);

    void emitException(final Throwable t);

    void complete();

}