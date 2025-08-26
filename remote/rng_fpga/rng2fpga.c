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




//Main
int main(){
    time_t t = time(NULL);
    struct tm tm = *localtime(&t);
    printf("%d-%02d-%02d %02d:%02d:%02d\n", tm.tm_year + 1900, tm.tm_mon + 1, tm.tm_mday, tm.tm_hour, tm.tm_min, tm.tm_sec);
    fflush(stdout);

	//printf("Open SwiftPro RNG device! \n");
	int fd = open("/dev/ttyRNG0", O_RDWR | O_NOCTTY);
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
    FILE *errorfile = fopen("/home/vq-user/rng_fpga/errorflag", "w");
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
	char *devname = "/dev/xdma0_h2c_1";
	int fpga_fd = open(devname,O_RDWR);
	if (fpga_fd < 0) {
		fprintf(stderr, "unable to open device %s, %d.\n",
			devname, fpga_fd);
		perror("open device");
		return -EINVAL;
	}
    signal(SIGINT, sigint_handler);
	while(1){
        char rbytes[16001];  
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
            FILE *errorfile = fopen("/home/vq-user/rng_fpga/errorflag", "w");
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
            int fd = open("/dev/ttyRNG0", O_RDWR | O_NOCTTY);
            if (fd < 0){
                printf("Could not reopen the USB! \n");
                return 1;
            }
        } 
		ret_write = write(fpga_fd, rbytes, 16000);
        if (ret_write!=16000){
		    printf("Wrong number of bytes written: %ld\n",ret_write);
        }
	}
	close(fpga_fd);
	close(fd);

}




