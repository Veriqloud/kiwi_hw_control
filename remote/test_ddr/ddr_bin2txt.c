#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

//union time {
//    char b[4];
//    uint32_t value;
//};
union global_counter {
    char b[8];
    uint64_t value;
};

int main(int argc, char *argv[]){
    if (argc < 3){
        printf("usage:\n ddr_bin2txt inputfile.bin outputfile.txt\n");
        return 0;
    }
    FILE *fp = fopen(argv[1], "r");
    FILE *ftxt = fopen(argv[2], "w");
    if (!fp){
        perror("fopen failed on bin file");
        return EXIT_FAILURE;
    }
    if (!ftxt){
        perror("fopen failed on txt file");
        return EXIT_FAILURE;
    }

    unsigned char buf[16];

    size_t ret = fread(buf, sizeof(*buf), 16, fp);
    if (ret != 16){
        fprintf(stderr, "fread failed %zu\n", ret);
    }
    uint32_t time;
    uint32_t idx;
    union global_counter gc;
    unsigned int result = 0;
    
    int count = 0;
    while (ret == 16){
        gc.value = 0;
        gc.b[0] = buf[0];
        gc.b[1] = buf[1];
        gc.b[2] = buf[2];
        gc.b[3] = buf[3];
        gc.b[4] = buf[4];
        gc.b[5] = buf[5];
        result = ((int) buf[6]) & 0xff;
        fprintf(ftxt, "%lu\t%lu\t%d\n", gc.value, gc.value%32, result);
        //printf("time %d\n", time);
        //printf("idx %d\n", idx);
        //printf("gc %lu\n", gc.value);
        //for (int i=0; i<16; i++){
        //    printf("buf[%d] %d\n", i, buf[i]);
        //}
        ret = fread(buf, sizeof(*buf), 16, fp);
        count ++;
        if (count > 10000000){
            printf("Aborting: more than 10M values\n");
            return 0;
        }
    }

    fclose(ftxt);
    fclose(fp);

    //time = (buf[0] << 24) | (buf[1] << 16) | (buf[2] << 8) | buf[3];
    //gc = (buf[4]<<40) | (buf[5]<<32) | (buf[6]<<24) | (buf[7]<<16) | (buf[8]<<8) | buf[9];
    //printf("time %d\n", t.value);
    //printf("gc %lu\n", gc.value);
    //printf("result %d\n", result);
    //}
}
