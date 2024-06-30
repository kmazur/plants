package pl.kmazur.plants.config;

@FunctionalInterface
public interface ReadableConfig {

    String get(final String key);

    default String get(final String key, final String defaultValue) {
        String value = get(key);
        return value != null ? value : defaultValue;
    }

}
