package pl.kmazur.plants.rxnew;

import pl.kmazur.plants.rxnew.function.FloatSupplier;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

public class CpuTempSource implements FloatSupplier {

    private static final Path TEMP_SOURCE_PATH = Paths.get("/sys/class/thermal/thermal_zone0/temp");

    @Override
    public float getAsFloat() {
        try {
            String content = Files.readString(TEMP_SOURCE_PATH);
            return Float.parseFloat(content);
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

}
