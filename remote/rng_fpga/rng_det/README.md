### How to generate test RNG data
- Read from Swiftpro USB device to have 16000 bytes of data, read out in a file rng.txt
```
$sudo ./rng2file
```
- Using xxd command to format data into ONE LINE
```
$xxd -E -ps -c 100000 rng.txt rng_ascii.txt
```
- Read from rng_ascii.txt file and push to xdma_hc2_1 device 
fgets() function in C read one line by one and endofline character. Better read from one line
```
$sudo ./rngdet
```
