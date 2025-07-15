import subprocess, os, sys, argparse
import time

def Write(base_add, value):
    str_base = str(base_add)
    str_value = str(value)
    command ="../../../tools/reg_rw /dev/xdma0_user "+ str_base + " w "+ str_value 
    #print(command)
    s = subprocess.check_call(command, shell = True)

def Read(base_add):
    str_base = str(base_add)
    command ="../../../tools/reg_rw /dev/xdma0_user "+ str_base + " w "+ "| grep  \"Read.*:\" | sed 's/Read.*: 0x\([a-z0-9]*\)/\\1/'" 
    #print(command)
    s = subprocess.check_output(command, shell = True)
    return s
def Write_stream_rng(file, size, count):
    str_file = file
    str_size = str(size)
    str_count = str(count)
    command ="../../../tools/dma_to_device -d /dev/xdma0_h2c_1 -f "+ str_file + " -s "+ str_size + " -c " + str_count 
    print(command)
    s = subprocess.check_call(command, shell = True)

def Read_stream_rng(file, size, count):
    str_file = file
    str_size = str(size)
    str_count = str(count)
    command ="../../../tools/dma_from_device -d /dev/xdma0_c2h_1 -f "+ str_file + " -s "+ str_size + " -c " + str_count 
    print(command)
    s = subprocess.check_call(command, shell = True)

#def Generate_rng():
#    command ="./rng2file"
#    #print(command)
#    s = subprocess.check_call(command, shell = True)

def Rng_repeat():
    file = "tmp.txt"
    size = 5
    count = 1
    while True:
        Write_stream_rng(file,size,count)

if __name__ =="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rng_init",action="store_true",help="send rng data to fpga")

    args = parser.parse_args()
    if args.rng_init:
        #Generate_rng()
        Rng_repeat()
