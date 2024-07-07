package pl.kmazur.plants.task;

public interface Task {

    default String getName() {
        return this.getClass().getSimpleName();
    }

    void run();

}
