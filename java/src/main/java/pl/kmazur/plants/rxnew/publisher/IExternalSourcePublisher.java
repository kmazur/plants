package pl.kmazur.plants.rxnew.publisher;

public interface IExternalSourcePublisher<T> extends IExternalNotificationPublisher<T> {

    void publish(final T element);


}