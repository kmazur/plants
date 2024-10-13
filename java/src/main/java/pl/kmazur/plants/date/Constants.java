package pl.kmazur.plants.date;

import java.time.format.DateTimeFormatter;

public final class Constants {
    public static final DateTimeFormatter FORMATTER = DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss");

    private Constants() {
        throw new AssertionError("Prevent new instance creation");
    }
}
