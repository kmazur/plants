package pl.kmazur.plants.time;

import java.time.ZoneId;

public class SystemTimeProvider implements ITimeProvider {

    @Override
    public ZoneId getZoneId() {
        return ZoneId.systemDefault();
    }

    @Override
    public long getCurrentMillis() {
        return System.currentTimeMillis();
    }

}
