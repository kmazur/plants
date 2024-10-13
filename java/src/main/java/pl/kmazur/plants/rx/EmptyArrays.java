package pl.kmazur.plants.rx;

public final class EmptyArrays {

    private static final Object[] EMPTY_ARRAY = new Object[0];

    public static <T> T[] emptyArray() {
        //noinspection unchecked
        return (T[]) EMPTY_ARRAY;
    }

    private EmptyArrays() {
        throw new AssertionError("Prevent new instance creation!");
    }


}
