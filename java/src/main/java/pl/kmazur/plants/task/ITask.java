package pl.kmazur.plants.task;

public interface ITask {

    default String getName() {
        return this.getClass().getSimpleName();
    }

    void run();

}
