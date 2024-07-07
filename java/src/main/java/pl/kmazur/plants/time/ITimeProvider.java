package pl.kmazur.plants.time;

import java.time.*;

public interface TimeProvider {

    ZoneId getZoneId();

    long getCurrentMillis();

    default ZonedDateTime getCurrentZonedDateTime() {
        return ZonedDateTime.ofInstant(
                Instant.ofEpochMilli(getCurrentMillis()),
                getZoneId()
        );
    }

    default LocalDateTime getCurrentLocalDateTime() {
        return getCurrentZonedDateTime().toLocalDateTime();
    }

}
