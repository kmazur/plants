package pl.kmazur.plants.rxnew;

import lombok.extern.slf4j.Slf4j;
import org.reactivestreams.Processor;
import org.reactivestreams.Subscriber;
import org.slf4j.event.Level;
import pl.kmazur.plants.rxnew.flow.FlowBuilder;
import pl.kmazur.plants.rxnew.function.FloatSupplier;
import pl.kmazur.plants.rxnew.processor.Slf4jLoggingProcessor;
import pl.kmazur.plants.rxnew.publisher.FanOutPublisher;
import pl.kmazur.plants.rxnew.publisher.IOnDemandPublisher;
import pl.kmazur.plants.rxnew.publisher.SupplierPublisher;
import pl.kmazur.plants.rxnew.source.CpuTempSource;
import pl.kmazur.plants.rxnew.subscriber.AutoRequestSubscriber;
import pl.kmazur.plants.rxnew.subscriber.DelegatingSubscriber;
import pl.kmazur.plants.rxnew.subscriber.FlowLimiterSubscriber;
import pl.kmazur.plants.rxnew.subscriber.IFlowLimiterSubscriber;
import pl.kmazur.plants.rxnew.subscriber.ISuspendableSubscriber;
import pl.kmazur.plants.rxnew.subscriber.SuspendableSubscriber;

import java.util.function.Consumer;

@Slf4j
public class Example {
    public static void main(String[] args) {
        final FloatSupplier             tempSource = new CpuTempSource();
        final IOnDemandPublisher<Float> publisher  = new SupplierPublisher<>(tempSource::getAsFloat, new FanOutPublisher<>());

        final Consumer<Float>               floatConsumer     = f -> log.info("Cpu temperature is: {}", f);
        final Subscriber<Float>             floatSubscriber   = DelegatingSubscriber.of(floatConsumer);
        final Subscriber<Float>             requestSubscriber = new AutoRequestSubscriber<>(floatSubscriber);
        final IFlowLimiterSubscriber<Float> subscriber1       = new FlowLimiterSubscriber<>(requestSubscriber);
        final ISuspendableSubscriber<Float> suspendable1      = new SuspendableSubscriber<>(subscriber1);

        final Processor<Float, Float> processor = new Slf4jLoggingProcessor<>("processor1", Level.INFO);

        FlowBuilder.from(publisher)
                .via(processor)
                .to(suspendable1);

        for (int i = 0; i < 10; i++) {
            publisher.publish();
        }
        subscriber1.release(1);

        System.out.println("suspending");
        suspendable1.suspend();
        System.out.println("publishing 3 elements");
        publisher.publish();
        publisher.publish();
        publisher.publish();
        System.out.println("releasing 3");
        subscriber1.release(3);
        System.out.println("resuming");
        suspendable1.resume();

        System.out.println("suspending");
        suspendable1.suspend();
        System.out.println("publisher -> complete");
        publisher.complete();
    }
}