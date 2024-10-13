package pl.kmazur.plants.rxnew.publisher;

import org.reactivestreams.Subscriber;

import java.util.function.Supplier;

public class SupplierPublisher<T> implements IOnDemandPublisher<T> {

    private final Supplier<T>                 supplier;
    private final IExternalSourcePublisher<T> publisher;

    public SupplierPublisher(final Supplier<T> supplier, IExternalSourcePublisher<T> publisher) {
        this.supplier  = supplier;
        this.publisher = publisher;
    }

    @Override
    public void subscribe(Subscriber<? super T> s) {
        publisher.subscribe(s);
    }

    @Override
    public void publish() {
        try {
            T element = supplier.get();
            if (element != null) {
                publisher.publish(element);
            }
        } catch (final Throwable t) {
            emitException(t);
        }
    }

    @Override
    public void emitException(Throwable t) {
        publisher.emitException(t);
    }

    @Override
    public void complete() {
        publisher.complete();
    }
}
