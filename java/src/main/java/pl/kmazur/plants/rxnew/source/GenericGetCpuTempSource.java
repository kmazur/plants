package pl.kmazur.plants.rxnew.source;

import oshi.SystemInfo;
import oshi.hardware.HardwareAbstractionLayer;
import oshi.hardware.Sensors;
import pl.kmazur.plants.rxnew.function.FloatSupplier;

public class GenericGetCpuTempSource implements FloatSupplier {

    private final Sensors sensors;

    public GenericGetCpuTempSource() {
        final SystemInfo               si  = new SystemInfo();
        final HardwareAbstractionLayer hal = si.getHardware();
        this.sensors = hal.getSensors();
    }

    @Override
    public float getAsFloat() {
        return (float) sensors.getCpuTemperature();
    }
}
