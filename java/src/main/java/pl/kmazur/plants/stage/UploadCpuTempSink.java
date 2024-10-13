package pl.kmazur.plants.stage;

import lombok.extern.slf4j.Slf4j;
import pl.kmazur.plants.rx.ISink;

@Slf4j
public class UploadCpuTempSink implements ISink<Float> {

    @Override
    public void accept(final Float value) {
        log.info("Uploading cpu temperature: {}", value);
    }

}
