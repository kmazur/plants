package pl.kmazur.plants.rx;

import pl.kmazur.plants.stage.UploadCpuTempSink;
import pl.kmazur.plants.time.ITimeProvider;
import pl.kmazur.plants.time.SystemTimeProvider;

import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

public class RxApp {

    public static void main(String[] args) {
        ITimeProvider timeProvider = new SystemTimeProvider();

        ScheduledExecutorService executorService = Executors.newScheduledThreadPool(1);

        PushSource<Float> periodicProducer = new PushSource<>();
        periodicProducer.subscribe(v -> System.out.println(v));

        executorService.scheduleAtFixedRate(() -> periodicProducer.produce((float) Math.random()), 0, 1, TimeUnit.SECONDS);

        ISink<Float> sink = new UploadCpuTempSink();
//        RunnableGraph<Float, Float> graph = new RunnableGraph<>(source, sink);
//        graph.run();
    }

}
