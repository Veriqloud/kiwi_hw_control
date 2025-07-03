#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <getopt.h>
#include <termios.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <errno.h>

#define DEVICE_NAME_C2H "/dev/xdma0_c2h_2"
#define DEVICE_NAME_H2C "/dev/xdma0_h2c_2"
#define SIZE_DEFAULT 16
#define COUNT_DEFAULT 64
//Main
static struct option const long_opts[] = {
	{"device_c2h", required_argument, NULL, 'd'},
	{"size", required_argument, NULL, 's'},
	{"count", required_argument, NULL, 'c'},
	{"device_h2c", required_argument, NULL, 'f'},
	{"help", no_argument, NULL, 'h'},
	{"verbose", no_argument, NULL, 'v'},
	{0, 0, 0, 0}
};
static uint64_t write_from_buffer(int fd, char *buffer, uint64_t size);
static uint64_t read_to_buffer(int fd, char *buffer, uint64_t size);
static uint64_t getopt_integer(char *optarg);
static void usage(const char *name)
{
	int i = 0;
	fprintf(stdout, "%s\n\n", name);
	fprintf(stdout, "usage: %s [OPTIONS]\n\n", name);
	fprintf(stdout, "Size and count are default, optionally save output to a file\n\n");

	fprintf(stdout, "  -%c (--%s) device to read data from (defaults to %s)\n",
		long_opts[i].val, long_opts[i].name, DEVICE_NAME_C2H);
	i++;
	fprintf(stdout,
		"  -%c (--%s) size of a single transfer in bytes, default %d.\n",
		long_opts[i].val, long_opts[i].name, SIZE_DEFAULT);
	i++;
	fprintf(stdout, "  -%c (--%s) number of transfers, default is %d.\n",
	       long_opts[i].val, long_opts[i].name, COUNT_DEFAULT);
	i++;
	fprintf(stdout,
		"  -%c (--%s) device to write the data of the transfers %s\n",
		long_opts[i].val, long_opts[i].name, DEVICE_NAME_H2C);
	i++;
	fprintf(stdout, "  -%c (--%s) print usage help and exit\n",
		long_opts[i].val, long_opts[i].name);
	i++;
	fprintf(stdout, "  -%c (--%s) verbose output\n",
		long_opts[i].val, long_opts[i].name);
	i++;

	fprintf(stdout, "\nReturn code:\n");
	fprintf(stdout, "  0: all bytes were dma'ed successfully\n");
	fprintf(stdout, "  < 0: error\n\n");
}

int main(int argc, char *argv[])
{
	int cmd_opt;
	char *device_c2h = DEVICE_NAME_C2H;
	char *device_h2c = DEVICE_NAME_H2C;
	uint64_t size = SIZE_DEFAULT;
	uint64_t count = 0;
	//char *ofname = NULL;
	uint64_t rc = 0;
	uint64_t rc_wr = 0;
	int fpga_fd_c2h;
	int fpga_fd_h2c;
	//int out_fd = -1;
	uint64_t buf_size = SIZE_DEFAULT;
	char buffer[SIZE_DEFAULT]= " "; //Does not support variable size for array, using mem will be slow
	int verbose = 1;


	while ((cmd_opt = getopt_long(argc, argv, "vhc:f:d:s:", long_opts,
			    NULL)) != -1) {
		switch (cmd_opt) {
		case 0:
			/* long option */
			break;
		case 'd':
			/* device node name */
			device_c2h = strdup(optarg);
			break;
		case 's':
			/* RAM size in bytes */
			size = getopt_integer(optarg);
			break;
		case 'c':
			count = getopt_integer(optarg);
			break;
			/* count */
		case 'f':
			device_h2c = strdup(optarg);
			break;
			/* print usage help and exit */
		case 'v':
			verbose = 1;
			break;
		case 'h':
		default:
			usage(argv[0]);
			exit(0);
			break;
		}
	}
	//if (verbose)
	//fprintf(stdout,
	//	"dev %s, output %s, size 0x%lx, count %lu\n", device,ofname, size, count);
	

	fpga_fd_c2h = open(device_c2h, O_RDWR);
	if (fpga_fd_c2h < 0){
		fprintf(stderr, "can not open the xdma_c2h device!\n");
		exit(1);
		return -EINVAL;
	}
	//create a file to store data
	fpga_fd_h2c = open(device_h2c, O_RDWR);
	if (fpga_fd_h2c < 0){
		fprintf(stderr, "can not open the xdma_c2h device!\n");
		exit(1);
		return -EINVAL;
	}
	//uint64_t count_loop = count;
	uint64_t rc_loop = 0;
	//for (int j = 0; j<count; j++){ //1 transfer
	while(1){
		rc = read_to_buffer(fpga_fd_c2h, buffer,buf_size);
		rc_wr = write_from_buffer(fpga_fd_h2c, buffer,buf_size);
		//printf("return read bytes: %ld\n", rc);
		//for (int k = 0; k<rc; k++){
		//	printf("%02x ", buffer[k]&0xff);
		//}
		//printf("\n");
		//if (fpga_fd_h2c >= 0){
			//usleep(1);
			//rc = write_from_buffer(fpga_fd_h2c, buffer,buf_size);
			//Printing to verify
			//printf("\nreturn written bytes: %ld\n", rc);
			//printf("Gc: %lx\n", ((uint64_t)buffer[0]&0xff) | ((uint64_t)(buffer[1]&0xff)<<8) | ((uint64_t)(buffer[2]&0xff)<<16) | ((uint64_t)(buffer[3]&0xff)<<24) | ((uint64_t)(buffer[4]&0xff)<<32) | ((uint64_t)(buffer[5]&0xff)<<40));
			//printf("Gc(int): %ld\n", ((uint64_t)buffer[0]&0xff) | ((uint64_t)(buffer[1]&0xff)<<8) | ((uint64_t)(buffer[2]&0xff)<<16) | ((uint64_t)(buffer[3]&0xff)<<24) | ((uint64_t)(buffer[4]&0xff)<<32) | ((uint64_t)(buffer[5]&0xff)<<40));
			//printf("Result: %x\n", buffer[6]&0xff);
			//for (int h = 0; h<rc; h++){
			//	printf("%02x ",buffer[h]&0xff);
			//}
			//printf("\n");
		//}

		rc_loop = rc_loop + rc;
	}

	//printf("return total read  bytes: %ld\n", rc_loop);
	close(fpga_fd_c2h);
	close(fpga_fd_h2c);
	//return rc_loop;
}

uint64_t write_from_buffer(int fd, char *buffer, uint64_t size)
{
	ssize_t rc;
	char *buf = buffer;
	rc = write(fd,buf,size);
	if (rc<0){
		fprintf(stderr,"writing to fail fails");
		perror("write file");
		exit(1);
		return -EIO;
	}
	if (rc != size)  {
		fprintf(stderr, "write to file underflow");
		exit(1);
	}
	return rc;
}

uint64_t read_to_buffer(int fd, char *buffer, uint64_t size)
{
	ssize_t rc;
	uint64_t count = 0;
	char *buf = buffer;
	rc = read(fd, buf, size);
	if (rc < 0) {
		fprintf(stderr,"reading data from fd to buffer fails!");
		perror("read file");
		exit(1);
		return -EIO;
	}
	if (rc != size){
		fprintf(stderr,"read underflow");
		exit(1);
	}
	return rc;
}
uint64_t getopt_integer(char *optarg)
{
	int rc;
	uint64_t value;

	rc = sscanf(optarg, "0x%lx", &value);
	if (rc <= 0)
		rc = sscanf(optarg, "%lu", &value);
	//printf("sscanf() = %d, value = 0x%lx\n", rc, value);

	return value;
}
