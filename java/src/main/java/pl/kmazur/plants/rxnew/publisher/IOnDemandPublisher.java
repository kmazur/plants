package pl.kmazur.plants.rxnew.publisher;

import org.reactivestreams.Publisher;

public interface IOnDemandPublisher<T> extends Publisher<T> {
    void publish();
}
