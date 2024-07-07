package pl.kmazur.plants.rxnew;

import oshi.SystemInfo;
import oshi.hardware.HardwareAbstractionLayer;
import oshi.hardware.Sensors;
import pl.kmazur.plants.rxnew.function.FloatSupplier;

public class GenericGetCpuTempSource implements FloatSupplier {

    private final Sensors sensors;

    public GenericGetCpuTempSource() {
        SystemInfo si = new SystemInfo();
        HardwareAbstractionLayer hal = si.getHardware();
        this.sensors = hal.getSensors();
    }

    @Override
    public float getAsFloat() {
        return (float) sensors.getCpuTemperature();
    }
}
