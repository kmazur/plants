package pl.kmazur.plants.rx;

import lombok.RequiredArgsConstructor;

import java.util.Iterator;

@RequiredArgsConstructor
public class IteratorSource<T> implements IPullSource<T> {

    private final Iterator<T> iterator;

    @Override
    public T pull() {
        if (iterator.hasNext()) {
            return iterator.next();
        }
        return null;
    }
}
