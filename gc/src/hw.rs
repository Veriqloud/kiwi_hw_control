use std::net::TcpStream;
use std::path::PathBuf;
use std::env::var;
use std::fs::{File, OpenOptions};
use memmap::MmapOptions;
use std::{thread, time};
use std::io::prelude::*;


// get value for fiber delay from file
fn get_fiber_delay() -> u32 {
    let mut tmpfile = PathBuf::from(
        var("CONFIGPATH").expect("os variable CONFIGPATH"));
    tmpfile.push("tmp.txt");
    let mut file = File::open(tmpfile).expect("opening tmp.txt");
    let mut contents = String::new();
    file.read_to_string(&mut contents).expect("get_fiber_delay: read to string");
    let mut get_next = false;

    // go through the lines and look for the matching word, then take the integer next to it
    for line in contents.lines(){
        for word in line.split("\t"){
            if get_next {
                let delay:u32 = word.parse()
                    .expect("could not parse string to int reading tmp.txt");
                return delay
            }
            match word {
                "fiber_delay" => {get_next = true;}
                _ => {break;}
            }
        }
    }
    panic!("Did not find fiber_delay in tmp.txt");
}

// get value for decoy delay from file
fn get_decoy_delay() -> u32 {
    let mut tmpfile = PathBuf::from(
        var("CONFIGPATH").expect("os variable CONFIGPATH"));
    tmpfile.push("tmp.txt");
    let mut file = File::open(tmpfile).expect("opening tmp.txt");
    let mut contents = String::new();
    file.read_to_string(&mut contents).expect("get_decoy_delay: read to string");
    let mut get_next = false;

    // go through the lines and look for the matching word, then take the integer next to it
    for line in contents.lines(){
        for word in line.split("\t"){
            if get_next {
                let delay:u32 = word.parse()
                    .expect("could not parse string to int reading tmp.txt");
                return delay
            }
            match word {
                "decoy_delay" => {get_next = true;}
                _ => {break;}
            }
        }
    }
    panic!("Did not find fiber_delay in tmp.txt");
}


// write to fpga
fn xdma_write(addr: usize, value: u32, offset: u64) {
    // we write single values to a memory mapped file
    // addr and offset are with respect to bytes; datatype is u32
    assert!(addr%4 == 0);
    let file = OpenOptions::new().read(true).write(true).open("/dev/xdma0_user").expect("opening /dev/xdma0_user");
    
    // there is no "safe" way to modify a single value on the FPGA memory file 
    unsafe {
        let mut mmap = MmapOptions::new().len(0x1000).offset(offset).map_mut(&file).expect("creating memory map");
        // move pointer and recast to u32
        let ptr = mmap.as_mut_ptr().add(addr) as *mut u32;
        ptr.write(value);
    };
}

// read from fpga
fn xdma_read(addr: usize, offset: u64) -> u32{
    assert!(addr%4 == 0);
    let file = OpenOptions::new().read(true).open("/dev/xdma0_user").expect("opening /dev/xdma0_user");
    let value  =  unsafe{
        let mmap = MmapOptions::new().len(0x1000).offset(offset).map(&file).expect("creating memory map");
        // recast to u32
        let ptr = mmap.as_ptr().add(addr) as *const u32;
        ptr.read()
    };
    value
}

//fn get_counts() -> std::io::Result<u32>{
//    let counts = xdma_read(56+8, 0);
//    Ok(counts)
//}


// write some parameters to the fpga (see fpga doc)
fn ddr_data_reg(command: u32, gc_delay: u32, decoy_delay: u32, delay_ab: u32){
    let offset = 0x1000;
    let fiber_delay = (gc_delay + 1) / 2;
    let pair_mode = (gc_delay + 1) % 2;
    let decoy_delay = (decoy_delay + 1) / 2;
    let decoy_pair_mode = (decoy_delay + 1) % 2;
    xdma_write(8, command, offset);
    xdma_write(16, 0, offset);
    xdma_write(20, 0, offset);
    xdma_write(32, 100, offset); // read speed
    xdma_write(36, 4000, offset); // threshold full
    xdma_write(40, (decoy_delay<<16) + fiber_delay, offset);
    xdma_write(44, delay_ab, offset);
    xdma_write(24, (decoy_pair_mode<<2) + (pair_mode<<1), offset);
    // enable register setting
    xdma_write(12, 0, offset);
    xdma_write(12, 1, offset);
}

fn ddr_data_init(){
    // reset module
    xdma_write(0, 0, 0x1000);
    xdma_write(16, 0, 0x12000);
    xdma_write(16, 1, 0x12000);
    thread::sleep(time::Duration::from_millis(100));
}

// reset and start ddr stuff
pub fn init_ddr(alice: bool){
    let fiber_delay = get_fiber_delay();
    let decoy_delay;
    if alice {
        decoy_delay = get_decoy_delay();
        println!("{:?}", decoy_delay);
    } else {
        decoy_delay = fiber_delay;
    }
    println!("decoy delay: {:?}", decoy_delay);
    // we have to add 64 to the delay due to some latency in the fpga
    ddr_data_reg(4, fiber_delay, decoy_delay, 50000);
    ddr_data_reg(3, fiber_delay, decoy_delay, 50000);
    ddr_data_init();
    println!("init ddr done");
}

// wait for the syncronization pulse (pps)
pub fn wait_for_pps(){
    loop {
        let pps = xdma_read(48, 0x1000);
        if pps == 1{ return };
    }
}

// syncronize at next pps
pub fn sync_at_pps(){
    // start to write
    xdma_write(0, 0, 0x1000);
    xdma_write(0, 1, 0x1000);
    
    // reset fifo gc_out
    xdma_write(28, 0, 0x1000);
    xdma_write(28, 1, 0x1000);
    
    // enable save alpha
    xdma_write(24, 0, 0x1000);
    xdma_write(24, 1, 0x1000);
    //thread::sleep(time::Duration::from_secs(1));
}


// separate gc from result bit; return as integers
fn split_gcr(buf_gcr: [u8;8]) -> (u64, u8){
    let mut buf = buf_gcr;
    buf[6] = 0;
    buf[7] = 0;
    let mut gc = u64::from_le_bytes(buf);
    gc = gc*2 + (buf_gcr[6] & 1) as u64;
    let result = (buf_gcr[6] >> 1) & 1;
    return (gc, result)
}

// format gc value before writing back to fpga; return as buf
fn gc_for_fpga(gc: u64) -> [u8;16]{
    let gc_mod = gc/2;
    let byte6 = gc % 2;
    let mut buf: [u8;16] = (gc_mod as u128).to_le_bytes();
    buf[6] = byte6 as u8;
    return buf
}

const BATCHSIZE: usize = 32; // number of clicks to process in one batch

// read gcr from fpga and split gc and r
pub fn process_gcr_stream(file: &mut File) -> std::io::Result<([u64; BATCHSIZE], [u8; BATCHSIZE])>{
    let mut buf: [u8; BATCHSIZE*16] = [0; BATCHSIZE*16];
    file.read_exact(&mut buf)?;
    let mut gc: [u64; BATCHSIZE] = [0; BATCHSIZE];
    let mut result: [u8; BATCHSIZE] = [0; BATCHSIZE];
    for i in 0..BATCHSIZE{
        (gc[i], result[i]) = split_gcr(buf[i*16..i*16+8].try_into().unwrap());
    }
    Ok((gc, result))
}


// write gc back to fpga
pub fn write_gc_to_fpga(gc: [u64; BATCHSIZE], file: &mut File) -> std::io::Result<()>{
    let mut buf: [u8; BATCHSIZE*16] = [0; BATCHSIZE*16];
    for i in 0..BATCHSIZE{
        let gcbuf = gc_for_fpga(gc[i]);
        buf[i*16..(i+1)*16].copy_from_slice(&gcbuf);
    }
    file.write_all(&buf)?;
    Ok(())
}

// write gc to Alice
pub fn write_gc_to_alice(gc: [u64; BATCHSIZE], alice: &mut TcpStream) -> std::io::Result<()>{
    let mut buf: [u8; BATCHSIZE*8] = [0; BATCHSIZE*8];
    for i in 0..BATCHSIZE{
        let gcbuf = gc[i].to_le_bytes();
        buf[i*8..(i+1)*8].copy_from_slice(&gcbuf);
    }
    alice.write_all(&buf)?;
    Ok(())
}



// read gc coming from Bob
pub fn read_gc_from_bob(bob: &mut TcpStream) -> std::io::Result<[u64;BATCHSIZE]>{
    let mut buf: [u8; BATCHSIZE*8] = [0; BATCHSIZE*8];
    let mut gc: [u64; BATCHSIZE] = [0; BATCHSIZE];
    bob.read_exact(&mut buf)?;
    for i in 0..BATCHSIZE{
        gc[i] = u64::from_le_bytes(buf[i*8..(i+1)*8].try_into().expect("converting gc from bob to u64"));
    }
    Ok(gc)
}











