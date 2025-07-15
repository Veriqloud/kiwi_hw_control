#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <termios.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <errno.h>

//Main
int main(){
	//printf("Open SwiftPro RNG device! \n");
	int fd = open("/dev/ttyACM0", O_RDWR | O_NOCTTY);
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
	} else{				    
	       	//printf("read successful\n");
	}	        
        //printf("Our device is: %s\n", buf);
        //printf("status byte: %d\n", buf[8]);

//Make file to store data
	char *filename = "rng.txt";
	FILE *fd_rng = fopen(filename, "w+");
	if (fd_rng == NULL){
		printf("Error opening the file %s",filename);
		return -1;
	}
	//while(1){
        for (int j = 0; j<1; j++){
                uint8_t rbytes[16001];  
                if (write(fd, "x", 1) != 1) {
			printf("Could not write the data request command!\n");
    			return 1;
			exit(0);
		}
		int n = 0;
		int N = 16001;  
		int i = 0;
		while (i < N-1){
			n = read(fd, rbytes + i, N-i);
		        printf("Number of bytes read: %d\n", n);
			i = i + n;
		}
		for (int k = 0; k < 16000; k++){
			uint32_t number = rbytes[k];
			//printf("%d",number);
			//printf("%d\n",k);
			fprintf(fd_rng, "%c",number);
		}
	}
	fclose(fd_rng);
	close(fd);
//
//Send rng data to xdma_h2c0
	//char *devname = "/dev/xdma0_h2c_1";
	//int fpga_fd = open(devname,O_RDWR);
	//if (fpga_fd < 0) {
	//	fprintf(stderr, "unable to open device %s, %d.\n",
	//		devname, fpga_fd);
	//	perror("open device");
	//	return -EINVAL;
	//}
	//while(1){
        ////for (int j = 0; j<1; j++){
        //        char rbytes[16001];  
        //        if (write(fd, "x", 1) != 1) {
	//		printf("Could not write the data request command!\n");
    	//		return 1;
	//		exit(0);
	//	}
	//	ssize_t ret_write;
	//	int n_rd = 0;
	//	int N = 16001;
	//	int i = 0;
	//	while (i < N-1) {
	//		n_rd = read(fd, rbytes+i, N-i);
	//		//printf("Number of bytes read: %d\n", n_rd);
	//		i = i + n_rd;

	//	}
	//	ret_write = write(fpga_fd, rbytes, 16000);
	//	printf("Number of bytes written: %ld\n",ret_write);
		//for (int k = 0; k < 16001; k++){
		//	char number = rbytes[k];
		//	char number_c[1];
		//	strcpy(number_c,"ab");
		//	rc_write = write(fpga_fd,number_c,1);
		        //printf("%c\n",number);
		        //printf("%d\n",k);
			//if (rc_write != 0) {
			//	printf("could not write to xdma device!\n");
			//	return 1;
			//	exit(0);
			//}
		      //printf("%d\n",number);
		      //printf("%d\n",k);
		      //fprintf(fd_rng, "%c",number);
		//}
	//}
	//close(fpga_fd);
	//close(fd);

}




