package pl.kmazur.plants.config;

public interface TypedConfig extends Config {

    default int getInt(final String key, final int defaultValue) {
        String value = get(key);
        return value != null ? Integer.parseInt(value) : defaultValue;
    }

    default int getOrSetInt(final String key, final int defaultValue) {
        String value = get(key);
        if (value == null) {
            set(key, Integer.toString(defaultValue));
            return defaultValue;
        }
        return Integer.parseInt(value);
    }

    default float getFloat(final String key, final float defaultValue) {
        String value = get(key);
        return value != null ? Float.parseFloat(value) : defaultValue;
    }

    default float getOrSetFloat(final String key, final float defaultValue) {
        String value = get(key);
        if (value == null) {
            set(key, Float.toString(defaultValue));
            return defaultValue;
        }
        return Float.parseFloat(value);
    }

}
