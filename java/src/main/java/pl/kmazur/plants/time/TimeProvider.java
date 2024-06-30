package pl.kmazur.plants.time;

import java.time.*;

public interface TimeProvider {

    ZoneId getZoneId();

    long getCurrentMillis();

    default ZonedDateTime getCurrentDateTime() {
        return ZonedDateTime.ofInstant(
                Instant.ofEpochMilli(getCurrentMillis()),
                getZoneId()
        );
    }

}
