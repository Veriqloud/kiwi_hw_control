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
//Send rng data to xdma_h2c0
	char *devname = "/dev/xdma0_h2c_1";
	int fpga_fd = open(devname,O_RDWR);
	if (fpga_fd < 0) {
		fprintf(stderr, "unable to open device %s, %d.\n",
			devname, fpga_fd);
		perror("open device");
		return -EINVAL;
	}
	//Open file rng_ascii.txt (content is 16000 random bytes), read and store content in a buffer
	FILE *fpointer;
	fpointer = fopen("rng_ascii.txt","r");
	char rng_string[16001];
	char rng_string_line[16001]; //Max length for one line
	if (fpointer == NULL) {
		printf("unable to open the rng_ascii.txt file");
		return -EINVAL;
	}
	//while(fgets(rng_string, 16000,fpointer) != NULL) {
	//	//printf("%s\n",rng_string);
	//	char number_c[16001];
	//	ssize_t rc_write;
	//	size_t nbytes;
	//	//strcpy(number_c,"ABCDEFGHabcdefghABCDEFGHabcdefghABCDEFGHabcdefghABCDEFGHabcdefgh");
	//	strcpy(number_c,rng_string);
	//	nbytes = strlen(number_c);
	//	//printf("%ld\n",nbytes);
	//	rc_write = write(fpga_fd,number_c,nbytes);
	//	printf("%ld\n",rc_write);
	//}
	while(1){
	//for (int j = 0; j<1; j++){
		char rbytes[16001];
		ssize_t ret_write;
		int N = 16001;
		int i = 0;
		int n = 0;
	        fgets(rng_string_line,sizeof(rng_string_line),fpointer);	
		i = strlen(rng_string_line);
		//printf("%d\n",i);
		//printf("%s\n",rng_string_line);
		char number_c[16001];
		size_t nbytes;
		strcpy(number_c,"ABCDEFGHabcdefghABCDEFGHabcdefghABCDEFGHabcdefghABCDEFGHabcdefghABCDEFGHabcdefghABCDEFGHabcdefghABCDEFGHabcdefghABCDEFGHabcdefgh");
		//strcpy(number_c,rng_string_line);
		nbytes = strlen(number_c);
		ret_write = write(fpga_fd, number_c, nbytes);
		printf("Number of written bytes: %ld\n", ret_write);
	}
	fclose(fpointer);
	//while(1){
        //        //char rbytes[16001];  
	//	//ssize_t ret_write;
	//	//int n_rd = 0;
	//	//int N = 16001;
	//	//int i = 0;
	//	//while (i < N-1) {
	//	//	///n_rd = read(fd, rbytes+i, N-i);
	//	//	rbytes+i = 
	//	//	//printf("Number of bytes read: %d\n", n_rd);
	//	//	i = i + n_rd;

	//	//}
	//	//ret_write = write(fpga_fd, rbytes, 16000);
	//	//printf("Number of bytes written: %ld\n",ret_write);
	//	//for (int k = 0; k < 16001; k++){
	//		char number_c[16001];
	//		ssize_t rc_write;
	//		size_t nbytes;
	//		//strcpy(number_c,"ABCDEFGHabcdefghABCDEFGHabcdefghABCDEFGHabcdefghABCDEFGHabcdefgh");
	//		strcpy(number_c,rng_string);
	//		nbytes = strlen(number_c);
	//		rc_write = write(fpga_fd,number_c,nbytes);
	//	        //printf("%c\n",number);
	//	        //printf("%d\n",k);
	//	        //if (rc_write != 0) {
	//	      	//	printf("could not write to xdma device!\n");
	//	      	//	return 1;
	//	      	//	exit(0);
	//	     	// }
	//	   	printf("%ld\n",rc_write);
	//	    //printf("%d\n",k);
	//	    //fprintf(fd_rng, "%c",number);
	//	//}
	//}
	close(fpga_fd);

}




