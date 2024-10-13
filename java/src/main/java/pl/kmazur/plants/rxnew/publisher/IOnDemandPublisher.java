package pl.kmazur.plants.rxnew.publisher;

public interface IOnDemandPublisher<T> extends IExternalNotificationPublisher<T> {
    void publish();
}
