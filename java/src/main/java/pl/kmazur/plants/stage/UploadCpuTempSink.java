package pl.kmazur.plants.rx;

import lombok.extern.slf4j.Slf4j;

@Slf4j
public class UploadCpuTempSink implements ISink<Float> {

    @Override
    public void accept(final Float value) {
        log.info("Uploading cpu temperature: {}", value);
    }

}
