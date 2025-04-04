use std::path::PathBuf;
use std::env::var;
use std::fs::{File, OpenOptions};
use memmap::MmapOptions;
use std::{thread, time};
use std::io::{prelude::*, BufReader};


// get value for fiber delay from file
fn get_fiber_delay() -> u32 {
    let mut tmpfile = PathBuf::from(
        var("CONFIGPATH").expect("os variable CONFIGPATH"));
    tmpfile.push("tmp.txt");
    let mut file = File::open(tmpfile).expect("opening tmp.txt");
    let mut contents = String::new();
    file.read_to_string(&mut contents).expect("get_fiber_delay: read to string");
    let mut get_next = false;
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

// write to fpga
fn xdma_write(addr: usize, value: u32, offset: u64) {
    // we write single values to a memory mapped file
    // addr and offset are with respect to bytes; datatype is u32
    assert!(addr%4 == 0);
    let file = OpenOptions::new().read(true).write(true).open("/dev/xdma0_user").expect("opening /dev/xdma0_user");
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

fn ddr_data_reg(command: u32, gc_delay: u32, delay_ab: u32){
    let offset = 0x1000;
    let fiber_delay = (gc_delay + 1) / 2;
    let pair_mode = (gc_delay + 1) % 2;
    xdma_write(8, command, offset);
    xdma_write(16, 0, offset);
    xdma_write(20, 0, offset);
    xdma_write(32, 2000, offset); // read speed
    xdma_write(36, 4000, offset); // threshold full
    xdma_write(40, fiber_delay, offset);
    xdma_write(44, delay_ab, offset);
    xdma_write(24, pair_mode<<1, offset);
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

pub fn init_ddr(){
    let fiber_delay = get_fiber_delay();
    ddr_data_reg(4, fiber_delay + 128, 5000);
    ddr_data_reg(3, fiber_delay + 128, 5000);
    ddr_data_init();
    println!("init ddr done");
}

pub fn wait_for_pps(){
    loop {
        let pps = xdma_read(48, 0x1000);
        if pps == 1{ return };
    }
}

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



pub fn process_stream(file: &mut BufReader<File>) -> std::io::Result<([u8;16], u64, u8)>{
    let mut buf: [u8;16] = [0;16];
    file.read_exact(&mut buf)?;
    let mut buf_for_gc: [u8;8] = buf[..8].try_into().unwrap();
    buf_for_gc[6] = 0;
    buf_for_gc[7] = 0;
    let mut gc = u64::from_le_bytes(buf_for_gc);
    gc = gc*2 + (buf[6] & 1) as u64;
    let result = (buf[6] >> 1) & 1;
    Ok((buf, gc, result))
}


pub fn gc_for_fpga(gc: u64) -> [u8;16]{
    let gc_mod = gc/2;
    let byte6 = gc % 2;
    let mut buf: [u8;16] = (gc_mod as u128).to_le_bytes();
    buf[6] = byte6 as u8;
    buf
}














