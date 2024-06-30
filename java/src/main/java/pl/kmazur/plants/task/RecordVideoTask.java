package pl.kmazur.plants.task;

import lombok.extern.slf4j.Slf4j;
import pl.kmazur.plants.camera.Camera;
import pl.kmazur.plants.config.AppConfig;
import pl.kmazur.plants.storage.Storage;
import pl.kmazur.plants.time.TimeProvider;

import java.nio.file.Path;
import java.time.ZonedDateTime;


@Slf4j
public class RecordVideoTask extends FileStagingTask {

    private final AppConfig config;
    private final TimeProvider timeProvider;
    private final Camera camera;

    public RecordVideoTask(AppConfig config, TimeProvider timeProvider) {
        super(config);
        this.config = config;
        this.timeProvider = timeProvider;
        this.camera = new Camera();
    }

    @Override
    public void doRun() {
        int segmentDurationSeconds = config.getInt("video.segment_duration_seconds", 300);
        String videoConfigFile = config.get("video-config-file");
        String imageConfigFile = config.get("image-config-file");


        log.info("Capturing image");
        ZonedDateTime now = timeProvider.getCurrentDateTime();

        camera.captureImage(imageConfigFile, getOutputFile("snapshot_").toString());

/*

  log "Capturing image"
  START_DATE_TIME="$(get_current_date_time_compact)"
  IMAGE_CAPTURE_FILE="snapshot_${START_DATE_TIME}.jpg"
  IMAGE_CAPTURE_PATH="$OUTPUT_STAGE_DIR/$IMAGE_CAPTURE_FILE"

  libcamera-still -c "$IMAGE_CONFIG_FILE" -o "$IMAGE_CAPTURE_PATH" -n -t 1 &> /dev/null
  log "Image captured at $START_DATE_TIME"

  LIGHT_LEVEL="$("$BIN_DIR/light_level" "$IMAGE_CAPTURE_PATH")"
  log "Light level is: $LIGHT_LEVEL"
  declare LIGHT_LEVEL_INT="${LIGHT_LEVEL%%.*}"

  LIGHT_LEVEL_FILE="light_level_${START_DATE_TIME}.txt"
  LIGHT_LEVEL_PATH="$OUTPUT_STAGE_DIR/$LIGHT_LEVEL_FILE"
  echo "$LIGHT_LEVEL_INT" > "$LIGHT_LEVEL_PATH"

  if [[ "$LIGHT_LEVEL_INT" -le "5" ]]; then
    log "Light level too low to record video: $LIGHT_LEVEL"

    if is_night; then
      SLEEP_LOW_LIGHT="$(( 20 * 60 ))"
      log "Sleeping for $SLEEP_LOW_LIGHT"
      sleep "$SLEEP_LOW_LIGHT"
      continue
    else
      log "Sleeping for $SEGMENT_DURATION_SECONDS"
      sleep "$SEGMENT_DURATION_SECONDS"
      continue
    fi
  fi

  log "Recording video for ${SEGMENT_DURATION_SECONDS} seconds"
  START_DATE_TIME="$(get_current_date_time_compact)"
  VIDEO_FILE_NAME="video_$START_DATE_TIME.h264"
  VIDEO_FILE_PATH="$OUTPUT_STAGE_DIR/$VIDEO_FILE_NAME"

  libcamera-vid -c "$VID_CONFIG_FILE" -t "${SEGMENT_DURATION_SECONDS}000" -o "$VIDEO_FILE_PATH"
  log "Done recording video"
 */

    }

    private Path getOutputFile(String file) {
        return getOutputPath().resolve(file);
    }

}
