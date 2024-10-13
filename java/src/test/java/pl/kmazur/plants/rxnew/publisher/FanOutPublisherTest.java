package pl.kmazur.plants.rxnew.publisher;

import org.junit.jupiter.api.TestInstance;
import org.reactivestreams.Publisher;
import org.reactivestreams.Subscriber;
import org.reactivestreams.tck.PublisherVerification;
import org.reactivestreams.tck.TestEnvironment;

@TestInstance(TestInstance.Lifecycle.PER_CLASS)
public class FanOutPublisherTest extends PublisherVerification<Integer> {


    public FanOutPublisherTest() {
        super(new TestEnvironment());
    }

    @Override
    public Publisher<Integer> createPublisher(long elements) {
        return new FanOutPublisher<>() {
            @Override
            public void subscribe(Subscriber<? super Integer> subscriber) {
                super.subscribe(subscriber);
                if (elements != Long.MAX_VALUE && elements != 2147483647L) {
                    for (int i = 0; i < elements; ++i) {
                        publish((int) (Math.random() * 1000));
                    }
                }
            }
        };
    }

    @Override
    public Publisher<Integer> createFailedPublisher() {
        FanOutPublisher<Integer> publisher = new FanOutPublisher<>();
        publisher.emitException(new RuntimeException("failure"));
        return publisher;
    }

    // ADDITIONAL CONFIGURATION

    @Override
    public long maxElementsFromPublisher() {
        return Long.MAX_VALUE - 1;
    }

    @Override
    public long boundedDepthOfOnNextAndRequestRecursion() {
        return 1;
    }
}