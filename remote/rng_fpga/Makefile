all: rng2fpga

rng2fpga: rng2fpga.c
	gcc -Wall -mrdseed -lcrypto $^ -o $@
