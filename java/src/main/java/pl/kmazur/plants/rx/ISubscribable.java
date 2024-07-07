package pl.kmazur.plants.rx;

import java.util.function.Consumer;

public interface IPushSource<T> {

    void subscribe(final Consumer<T> consumer);

}
