package pl.kmazur.plants.rx;

import java.util.stream.Stream;

public final class Sources {
    private Sources() {
        throw new AssertionError("Prevent new instance creation");
    }

    public static <T> IPullSource<T> from(final Iterable<T> iterable) {
        return new IteratorSource<>(iterable.iterator());
    }

    public static <T> IPullSource<T> from(Stream<T> stream) {
        return new IteratorSource<>(stream.iterator());
    }
}
