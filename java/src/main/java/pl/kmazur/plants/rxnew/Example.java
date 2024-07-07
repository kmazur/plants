package pl.kmazur.plants.rx2;

import pl.kmazur.plants.rx.SimpleSubscriber;
import pl.kmazur.plants.stage.CpuTempSource;
import pl.kmazur.plants.stage.FloatSupplier;
import pl.kmazur.plants.stage.GenericGetCpuTempSource;

public class Example {
    public static void main(String[] args) {
        FanOutPublisher<Float> publisher = new FanOutPublisher<>();

        SimpleSubscriber<Float> subscriber1 = new SimpleSubscriber<>();
        SimpleSubscriber<Float> subscriber2 = new SimpleSubscriber<>();

        publisher.subscribe(subscriber1);
        publisher.subscribe(subscriber2);

        FloatSupplier tempSource = new GenericGetCpuTempSource();
        for (int i = 0; i < 10; ++i) {
            float cpuTemp = tempSource.getAsFloat();
            publisher.publish(cpuTemp);
            try {
                Thread.sleep(1_000);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return;
            }
        }
    }
}