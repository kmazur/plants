package pl.kmazur.plants.rxnew.subscriber;

import org.reactivestreams.Subscriber;
import pl.kmazur.plants.rxnew.ISuspendable;

public interface ISuspendableSubscriber<T> extends Subscriber<T>, ISuspendable {

}
