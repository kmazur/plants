package pl.kmazur.plants.rx;

@FunctionalInterface
public interface IFlow<F, T> {

    T apply(final F value);
}
