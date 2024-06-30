package pl.kmazur.plants.storage;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

public final class Storage {

    private Storage() {
        throw new AssertionError("Prevent new instance creation");
    }

    public static boolean ensureDirExists(String dirPath) {
        Path dir = Paths.get(dirPath);
        return ensureDirExists(dir);
    }

    public static boolean ensureDirExists(Path dir) {
        try {
            Files.createDirectories(dir);
        } catch (IOException e) {
            // explicitly swallow exception
        }
        return Files.exists(dir);
    }

    public static boolean ensureFileExists(String filePath) {
        Path path = Paths.get(filePath);
        if (Files.notExists(path)) {
            try {
                Path parentDir = path.getParent();
                Files.createDirectories(parentDir);
                Files.createFile(path);
            } catch (IOException e) {
                // explicitly swallow exception
            }
        }
        return Files.exists(path);
    }


}
