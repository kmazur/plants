package pl.kmazur.plants.rxnew.publisher;

import org.reactivestreams.Publisher;

public interface IExternalNotificationPublisher<T> extends Publisher<T> {

    void emitException(final Throwable t);

    void complete();

}