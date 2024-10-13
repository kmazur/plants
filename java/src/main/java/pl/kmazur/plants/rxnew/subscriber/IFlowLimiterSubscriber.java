package pl.kmazur.plants.rxnew.subscriber;

import org.reactivestreams.Subscriber;

public interface IFlowLimiterSubscriber<T> extends Subscriber<T> {
    void closeFlow();

    void release(long request);

    default void limitTo(long request) {
        closeFlow();
        release(request);
    }

    void openFlow();
}
