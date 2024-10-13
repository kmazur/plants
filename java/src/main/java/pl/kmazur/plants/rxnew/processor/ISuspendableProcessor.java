package pl.kmazur.plants.rxnew.processor;

import org.reactivestreams.Processor;
import pl.kmazur.plants.rxnew.ISuspendable;

public interface ISuspendableProcessor<T, R> extends Processor<T, R>, ISuspendable {
}
