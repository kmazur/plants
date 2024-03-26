#include <stdio.h>
#include <stdlib.h>

#define MAX_SECONDS 86400  // Maximum number of seconds in a day

typedef struct {
    float min;
    float max;
    float sum;
    float last;
    int count;
} VolumeData;

VolumeData volumeData[MAX_SECONDS];

void initVolumeData() {
    for (int i = 0; i < MAX_SECONDS; ++i) {
        volumeData[i].min = 1e6;  // Initialize with a large number
        volumeData[i].max = -1e6; // Initialize with a small number
        volumeData[i].last = -1e6; // Initialize with a small number
        volumeData[i].sum = 0;
        volumeData[i].count = 0;
    }
}

int main(int argc, char *argv[]) {
    if (argc < 3) {
        fprintf(stderr, "Usage: %s <input_file> <output_file>\n", argv[0]);
        return EXIT_FAILURE;
    }

    FILE *fp = fopen(argv[1], "r");
    FILE *out = fopen(argv[2], "w");
    if (!fp || !out) {
        perror("Error opening file");
        return EXIT_FAILURE;
    }

    initVolumeData();

    float timestamp, volumeLevel;
    int lastSecond = -1;
    while (fscanf(fp, "%f\n%f\n", &timestamp, &volumeLevel) == 2) {
        int second = (int)timestamp;
        lastSecond = second;

        if (volumeLevel < volumeData[second].min) {
            volumeData[second].min = volumeLevel;
        }
        if (volumeLevel > volumeData[second].max) {
            volumeData[second].max = volumeLevel;
        }
        volumeData[second].sum += volumeLevel;
        volumeData[second].last = volumeLevel;
        volumeData[second].count += 1;
    }

    for (int i = 0; i <= lastSecond; ++i) {
        float mean = volumeData[i].sum / volumeData[i].count;
        fprintf(out, "%d %f %f %f %f\n", i, volumeData[i].min, volumeData[i].max, mean, volumeData[i].last);
    }

    fclose(fp);
    fclose(out);

    return EXIT_SUCCESS;
}