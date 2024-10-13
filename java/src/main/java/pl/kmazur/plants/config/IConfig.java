package pl.kmazur.plants.config;

public interface IConfig extends IReadableConfig, IWritableConfig {

    default String getOrSet(final String key, final String value) {
        String v = get(key);
        if (v == null) {
            set(key, value);
            return value;
        }
        return v;
    }


}
