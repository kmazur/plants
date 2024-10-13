package pl.kmazur.plants.rx;

import java.util.Collections;
import java.util.List;

public class RunnableGraph<F, T> {

    private final IPullSource<F> source;
    private final List<IFlow<F, T>> flows;
    private final ISink<T> sink;

    public RunnableGraph(IPullSource<F> source, List<IFlow<F, T>> flows, ISink<T> sink) {
        this.source = source;
        this.flows = flows;
        this.sink = sink;
    }

    public RunnableGraph(IPullSource<F> source, ISink<T> sink) {
        //noinspection unchecked
        this(source, Collections.singletonList(f -> (T) f), sink);
    }

    public void run() {
        F current;
        while ((current = source.pull()) != null) {
            for (IFlow<F, T> flow : flows) {
                T result = flow.apply(current);
                sink.accept(result);
            }
        }
    }

}
