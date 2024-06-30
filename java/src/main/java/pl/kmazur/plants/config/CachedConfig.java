package pl.kmazur.plants.config;

import java.util.HashMap;

public class CachedConfig implements TypedConfig {

    private final Config delegate;
    private final HashMap<String, String> map;

    public CachedConfig(final Config delegate) {
        this.delegate = delegate;
        this.map = new HashMap<>();
    }

    @Override
    public String get(String key) {
        String v = map.get(key);
        if (v != null) {
            return v;
        }

        String value = delegate.get(key);
        map.put(key, value);
        return value;
    }

    @Override
    public void set(String key, String value) {
        map.put(key, value);
    }

}
