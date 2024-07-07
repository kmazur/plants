package pl.kmazur.plants.config;

public interface Config extends ReadableConfig, WritableConfig {

    default String getOrSet(final String key, final String value) {
        String v = get(key);
        if (v == null) {
            set(key, value);
            return value;
        }
        return v;
    }


}
