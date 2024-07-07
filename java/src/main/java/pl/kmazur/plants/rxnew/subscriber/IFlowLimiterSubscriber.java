package pl.kmazur.plants.rxnew.subscriber;

import org.reactivestreams.Subscriber;

public interface IExternalSubscriber<T> extends Subscriber<T> {
    void release(long request);
}
