package pl.kmazur.plants.jmh;

import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.Fork;
import org.openjdk.jmh.annotations.Measurement;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.OutputTimeUnit;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.annotations.Warmup;
import org.openjdk.jmh.infra.Blackhole;

import java.util.concurrent.TimeUnit;

@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.NANOSECONDS)
@State(Scope.Thread)
@Warmup(iterations = 2)
@Measurement(iterations = 3)
@Fork(1)
public class NullCheckBenchmark {

    private Runnable a;
    private Runnable b;

    @Setup
    public void setup() {
        // Initialize 'a' as null or a no-op implementation for testing
        a = () -> {};
        b = () -> {};
    }

    @Benchmark
    public void testWithBranchCheck(Blackhole bh) {
        if (a != null) {
            a.run();
        }
        bh.consume(a);
    }

    @Benchmark
    public void testWithNoOp(Blackhole bh) {
        b.run();
        bh.consume(b);
    }

    public static void main(String[] args) throws Exception {
        org.openjdk.jmh.Main.main(args);
    }
}
