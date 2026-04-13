#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
//#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <termios.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <errno.h>
#include <signal.h>
#include <fcntl.h>
#include <time.h>
#include <immintrin.h>
#include <openssl/evp.h>
#include <string.h>

// this program takes true random numbers from a USB stick,
// xors them with PRNGs from the CPU
// and write to fpga

struct Config {
    char rng_target[64];
    int use_trng;
    char trng_source[64];
    int use_prng;
};

int print_config(struct Config *config){
    printf("rng_target\t\t%s\n", config->rng_target);
    printf("use_trng\t\t%d\n", config->use_trng);
    printf("trng_source\t\t%s\n", config->trng_source);
    printf("use_prng\t\t%d\n", config->use_prng);
    return 0;
}

int get_config(char *filename, struct Config *c){
    FILE *file = fopen(filename, "r");
    if (file == NULL) {
        perror("Error opening config file");
        return 1;
    }
    char line[128] = {0};

    while (fgets(line, sizeof(line), file)) {
        if ((line[0] == '#') | (line[0] == '\n')) {
            continue;
        } else {
            char s1[32] = {0};
            char s2[64] = {0};
            if (sscanf(line, "%31s %63s", s1, s2) == 2) {
                if (strcmp(s1, "rng_target") == 0) {
                    strcpy(c->rng_target, s2);
                } else if (strcmp(s1, "use_trng") == 0) {
                    if (strcmp("0", s2) == 0){
                        c->use_trng = 0;
                    } else {
                        c->use_trng = 1;
                    }
                } else if (strcmp(s1, "trng_source") == 0) {
                    strcpy(c->trng_source, s2);
                } else if (strcmp(s1, "use_prng") == 0) {
                    if (strcmp("0", s2) == 0){
                        c->use_prng = 0;
                    } else {
                        c->use_prng = 1;
                    }
                }
            } else {
                printf("config file format error in line: %s\n", line);
                return 1;
            }
        }
    }
    print_config(c);
    fclose(file);
    return 0;
}

// write a zeros to the fpga upon exit
void sigint_handler (int signum) {
	char *devname = "/dev/xdma0_h2c_1";
	int fpga_fd = open(devname,O_RDWR);
	if (fpga_fd < 0) {
		fprintf(stderr, "at sigint: unable to open device %s, %d.\n",
			devname, fpga_fd);
	} else {
        char buf = 0;
		write(fpga_fd, &buf, 1);
    }
    close(fpga_fd);
    _exit(0);
}

// true rng seed from CPU
void get_seed(uint8_t *seed, int len){
    unsigned long long *buf = (unsigned long long *)(seed);  // 256 bit
    for (int i=0; i<len/8; i++){
        while (_rdseed64_step(&buf[i])!=1){
            continue;
        }
    }
}

// aes expansion from seed
// expand seed by a factor of 256 
void aes_ctr_rng(uint8_t *buf, int len) {
    uint8_t seed[32] = {0};
    int batchsize = 8192;   // 256 * len(seed)
    uint8_t nonce[16] = {0}; // 128-bit IV (CTR nonce)
    
    int current_len = (batchsize < len) ? batchsize: len;
    int current_pos = 0;
    int len_left = len;
    // use a new seed every batch
    while (len_left>0){
        get_seed(seed, 32);
        EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
        if (!ctx) exit(1);
        EVP_EncryptInit_ex(ctx, EVP_aes_256_ctr(), NULL, seed, nonce);
        int outlen = 0;
        EVP_EncryptUpdate(ctx, buf+current_pos, &outlen, buf+current_pos, current_len);
        if (outlen != current_len) {
            printf("[aes_ctr_rng] warning: expected outlen%i\t but got: %i\n", current_len, outlen);
        }
        current_pos += current_len;
        len_left = len-current_pos;
        current_len = (batchsize < len_left) ? batchsize : len_left;
        EVP_CIPHER_CTX_free(ctx);
    }
}



int main(int argc, char *argv[]){
    if (argc != 2) {
        printf("usage: rng2fpga <config_file>\n");
        return 0;
    }
    char *config_filename = argv[1];
    struct Config config = {0};
    if (get_config(config_filename, &config)) {
        printf("error in get_config()\n");
        return 0;
    }
    if (config.use_trng == 0) {
        printf("WARNING: trng is not used");
    }
    if (config.use_prng == 0) {
        printf("WARNING: prng is not used");
    }

    time_t t = time(NULL);
    struct tm tm = *localtime(&t);
    printf("%d-%02d-%02d %02d:%02d:%02d starting program\n", tm.tm_year + 1900, tm.tm_mon + 1, tm.tm_mday, tm.tm_hour, tm.tm_min, tm.tm_sec);
    fflush(stdout);

	//printf("Open SwiftPro RNG device! \n");
	int fd = open(config.trng_source, O_RDWR | O_NOCTTY);
	if (fd < 0){
		printf("Could not open the USB! \n");
		return 1;
	}else{
		//printf("Open successfully! \n");
	}

	// Write m to the device : to read 8bytes of the device name + status byte

	char buf[128] = "";	
	if (write(fd, "m", 1) != 1){
		printf("Could not write command! \n");
		return 1;
	}else{
		//printf("Write command successfully! \n");
	}

	struct termios opts;
	int retVal = tcgetattr(fd, &opts);
	//printf("retVal: %d\n", retVal);
       
    opts.c_lflag &= ~(ECHO | ECHONL | ICANON | ISIG | IEXTEN);
    opts.c_iflag &= ~(INLCR | IGNCR | ICRNL | IXON | IXOFF);
    opts.c_oflag &= ~(ONLCR | OCRNL);
	opts.c_cc[VTIME] = 1;
	opts.c_cc[VMIN] = 0;

	retVal = tcsetattr(fd, TCSANOW, &opts);
    if (retVal) {       
        printf("Could not set configuration for serial device\n");
        close(fd);
        return 1;
	}

	//Read Device name from RNG device

    if (read(fd, buf, 128) != 9) {
        printf("Could not read!\n");
        return 1;
	} 				    
    // create the errorfile and write the errorbyte in there (0 == no error)
    FILE *errorfile = fopen("/tmp/rng_errorflag", "w");
    if (errorfile == NULL) {
        fprintf(stderr, "unable to open errorflag file\n");
    }
    char error = buf[8];
    if (fwrite(&error, sizeof(char), 1, errorfile) != 1){
        fprintf(stderr, "unable to write to errorfile\n");
    }
    fclose(errorfile);
    if (buf[8] != 0){
        fprintf(stderr, "error byte was not 0; exiting.\n");
        return -1;
    }
        

    
    //Send rng data to xdma_h2c0
	char *devname = config.rng_target;
	int fpga_fd = open(devname,O_RDWR);
	if (fpga_fd < 0) {
		fprintf(stderr, "unable to open device %s, %d.\n",
			devname, fpga_fd);
		perror("open device");
		return -EINVAL;
	}
    signal(SIGINT, sigint_handler);
	while(1){
        char rbytes[16001] = {0};  
        uint8_t cpu_rbytes[16000] = {0};
        aes_ctr_rng(cpu_rbytes, 16000);

        if (write(fd, "x", 1) != 1) {
			printf("Could not write the data request command!\n");
    			return 1;
			exit(0);
		}
		ssize_t ret_write;
		int n_rd = 0;
		int N = 16001;
		int i = 0;
		while (i < N-1) {
			n_rd = read(fd, rbytes+i, N-i);
			//printf("Number of bytes read: %d\n", n_rd);
			i = i + n_rd;

		}
        char error = rbytes[16000];
        if (error){
            FILE *errorfile = fopen("/tmp/rng_errorflag", "w");
            if (errorfile == NULL) {
                fprintf(stderr, "unable to open errorflag file\n");
            }
            if (fwrite(&error, sizeof(char), 1, errorfile) != 1){
                fprintf(stderr, "unable to write to errorfile\n");
            }
            fclose(errorfile);
            printf("RNG ERROR. closing and reopening device %d\n", error);
            fflush(stdout);
	        close(fd);
            int fd = open(config.trng_source, O_RDWR | O_NOCTTY);
            if (fd < 0){
                printf("Could not reopen the USB! \n");
                return 1;
            }
        } 
        for (int i=0; i<16000; i++){
            rbytes[i] = rbytes[i] ^ cpu_rbytes[i];
        }
		ret_write = write(fpga_fd, rbytes, 16000);
        if (ret_write!=16000){
		    printf("Wrong number of bytes written: %ld\n",ret_write);
        }
	}
	close(fpga_fd);
	close(fd);

}




