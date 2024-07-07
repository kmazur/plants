import org.openjdk.jmh.annotations.*;

import java.util.concurrent.TimeUnit;

@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.NANOSECONDS)
@State(Scope.Thread)
public class NullCheckBenchmark {

    private Runnable a;

    @Setup
    public void setup() {
        // Initialize 'a' as null or a no-op implementation for testing
        a = null;
    }

    @Benchmark
    public void testWithBranchCheck() {
        if (a != null) {
            a.run();
        }
    }

    @Benchmark
    public void testWithNoOp() {
        a = () -> {}; // No-op implementation
        a.run();
    }

    public static void main(String[] args) throws Exception {
        org.openjdk.jmh.Main.main(args);
    }
}
