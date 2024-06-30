package pl.kmazur.plants.time;

public class SystemTimeProvider implements TimeProvider {

    @Override
    public long getCurrentMillis() {
        return System.currentTimeMillis();
    }

    public static void main(String[] args) {
        System.out.println(new SystemTimeProvider().getCurrentDateTime());
    }
}
