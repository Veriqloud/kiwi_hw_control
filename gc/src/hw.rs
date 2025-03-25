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
fn xdma_write(addr: u32, value: u32, offset: u32) -> std::io::Result<()>{
    let file = OpenOptions::new().read(true).write(true).open("/dev/xdma_user")?;
    unsafe {
        let mut mmap = MmapOptions::new()
            .len(0x1000)
            .offset(offset as u64)
            .map_mut(&file)?;
        let (_, mem, _) = mmap.align_to_mut::<u32>();
        //let mem = std::mem::transmute::<u8, u32>(&mmap);
        mem[(addr/4) as usize] = value;
    }
    Ok(())
}

// read from fpga
fn xdma_read(addr: u32, offset: u32) -> std::io::Result<u32>{
    let file = OpenOptions::new().read(true).open("/dev/xdma_user")?;
    unsafe {
        let mut mmap = MmapOptions::new()
            .len(0x1000)
            .offset(offset as u64)
            .map_mut(&file)?;
        let (_, mem, _) = mmap.align_to_mut::<u32>();
        //let mem = std::mem::transmute::<&u8, &u32>(mmap);
        return Ok(mem[(addr/4) as usize]);
    }
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




