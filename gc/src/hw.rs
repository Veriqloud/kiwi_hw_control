use std::fs::{File, OpenOptions};
use memmap::{MmapMut, MmapOptions};
use std::io::prelude::*;


// get value for fiber delay from file
fn get_fiber_delay() -> std::io::Result<u32> {
    let mut file = File::open("tmp.txt")?;
    let mut contents = String::new();
    file.read_to_string(&mut contents)?;
    let mut get_next = false;
    for line in contents.lines(){
        for word in line.split("\t"){
            if get_next {
                let delay:u32 = word.parse()
                    .expect("could not parse string to int reading tmp.txt");
                return Ok(delay)
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
fn xdma_write(addr: usize, value: u32, offset: u64) -> std::io::Result<()>{
    // we write single values to a memory mapped file
    // addr and offset are with respect to bytes; datatype is u32
    let file = OpenOptions::new().read(true).write(true).open("/dev/xdma_user")?;
    let mut mmap = unsafe {
        MmapOptions::new().len(0x1000).offset(offset).map_mut(&file)?;
    }
    // recast to u32
    let ptr = mmap.as_mut_ptr() as *mut [u32;0x400];
    let data = unsafe {&mut *ptr};
    data[addr/4] = value;
    Ok(())
}

// read from fpga
fn xdma_read(addr: usize, offset: u64) -> std::io::Result<u32>{
    let file = OpenOptions::new().read(true).open("/dev/xdma_user")?;
    let mmap = unsafe {
        MmapOptions::new().len(0x1000).offset(offset).map(&file)?;
    }
    let ptr = mmap.as_ptr() as *const [u32;0x400];
    let data = unsafe {& *ptr};
    Ok(data[addr/4])
}

fn get_counts() -> std::io::Result<u32>{
    let counts = xdma_read(56+8, 0)?;
    Ok(counts)
}

pub fn init_ddr() -> std::io::Result<()>{
    println!("flag1");
    let fiber_delay = get_fiber_delay()?;
    println!("counts {:?}", get_counts()?);
    Ok(())
}

pub fn sync_at_pps(){
}




