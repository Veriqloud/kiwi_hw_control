use memmap::MmapOptions;
use std::fs::{File, OpenOptions, read_to_string};
use std::io::prelude::*;
use std::net::TcpStream;
use std::sync::OnceLock;
use std::{thread, time};
use std::time::{Instant};
use crate::config::Configuration;

pub const PPS_ADDRESS: usize = 48;
pub const PPS_OFFSET: u64 = 0x1000;

pub static CONFIG: OnceLock<Configuration> = OnceLock::new();

enum HwCurrentParam {
    FiberDelay,
    DecoyDelay,
}

impl ToString for HwCurrentParam {
    fn to_string(&self) -> String {
        match self {
            HwCurrentParam::FiberDelay => "fiber_delay".to_string(),
            HwCurrentParam::DecoyDelay => "decoy_delay".to_string(),
        }
    }
}

fn read_hw_current_int_param(param: &str, current_hw_params_file_path: &str) -> u32 {
    read_to_string(current_hw_params_file_path)
        .expect("current hardware parameters file could not be opened")
        .lines()
        .find_map(|l| {
            let mut parts = l.trim().split("\t");
            if parts.next().unwrap_or_default() == param {
                Some(
                    parts
                        .last()
                        .expect(format!("could not parse value for param: {param}").as_str())
                        .parse::<u32>()
                        .unwrap(),
                )
            } else {
                None
            }
        })
        .expect(format!("did not find param: {param}").as_str())
}

// write to fpga
fn xdma_write(addr: usize, value: u32, offset: u64) {
    // we write single values to a memory mapped file
    // addr and offset are with respect to bytes; datatype is u32
    assert!(addr % 4 == 0);

    let file = OpenOptions::new()
        .read(true)
        .write(true)
        .open(CONFIG.get().unwrap().fpga_start_socket_path.as_str())
        .expect(
            format!(
                "opening {}",
                CONFIG.get().unwrap().fpga_start_socket_path.as_str()
            )
            .as_str(),
        );

    // there is no "safe" way to modify a single value on the FPGA memory file
    unsafe {
        let mut mmap = MmapOptions::new()
            .len(0x1000)
            .offset(offset)
            .map_mut(&file)
            .expect("creating memory map");
        // move pointer and recast to u32
        let ptr = mmap.as_mut_ptr().add(addr) as *mut u32;
        ptr.write(value);
    };
}

// read from fpga
fn xdma_read(addr: usize, offset: u64) -> u32 {
    assert!(addr % 4 == 0);

    let file = OpenOptions::new()
        .read(true)
        .open(CONFIG.get().unwrap().fpga_start_socket_path.as_str())
        .expect(
            format!(
                "opening {}",
                CONFIG.get().unwrap().fpga_start_socket_path.as_str()
            )
            .as_str(),
        );
    let value = unsafe {
        let mmap = MmapOptions::new()
            .len(0x1000)
            .offset(offset)
            .map(&file)
            .expect("creating memory map");
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
fn ddr_data_reg(command: u32, gc_delay: u32, decoy_delay: u32, delay_ab: u32) {
    //println!("{:?} {:?}", gc_delay, decoy_delay);
    let offset = 0x1000;
    let fiber_delay = (gc_delay + 1) / 2;
    let pair_mode = (gc_delay + 1) % 2;
    let de_delay = (decoy_delay + 1) / 2;
    let de_pair_mode = (decoy_delay + 1) % 2;
    //println!("{:?} {:?} {:?} {:?}", fiber_delay, pair_mode, de_delay, de_pair_mode);
    xdma_write(8, command, offset);
    xdma_write(16, 0, offset);
    xdma_write(20, 0, offset);
    xdma_write(32, 100, offset); // read speed
    xdma_write(36, 4000, offset); // threshold full
    xdma_write(40, (de_delay << 16) | fiber_delay, offset);
    xdma_write(44, delay_ab, offset);
    xdma_write(24, (de_pair_mode << 2) | (pair_mode << 1), offset);
    // enable register setting
    xdma_write(12, 0, offset);
    xdma_write(12, 1, offset);
}

fn ddr_data_init() {
    // reset module
    xdma_write(0, 0, 0x1000);
    xdma_write(16, 0, 0x12000);
    thread::sleep(time::Duration::from_millis(100));
    xdma_write(16, 1, 0x12000);
    // sleep to give the simulator some time to reset the fifos
    thread::sleep(time::Duration::from_millis(500));
}

// reset and start ddr stuff
pub fn init_ddr(alice: bool) {
    let fiber_delay = read_hw_current_int_param(
        &HwCurrentParam::FiberDelay.to_string(),
        &CONFIG.get().unwrap().current_hw_parameters_file_path,
    );

    let decoy_delay = if alice {
        read_hw_current_int_param(
            &HwCurrentParam::DecoyDelay.to_string(),
            &CONFIG.get().unwrap().current_hw_parameters_file_path,
        )
    } else {
        fiber_delay
    };

    // we have to add 64 to the delay due to some latency in the fpga
    ddr_data_reg(4, fiber_delay, decoy_delay, 50000);
    ddr_data_reg(3, fiber_delay, decoy_delay, 50000);
    ddr_data_init();
    tracing::info!("init ddr done");
}

// wait for the syncronization pulse (pps)
pub fn wait_for_pps() {
    loop {
        let pps = xdma_read(PPS_ADDRESS, PPS_OFFSET);
        if pps == 1 {
            tracing::info!("got first pps");
            return;
        };
    }
}

// syncronize at next pps
pub fn sync_at_pps() {
    tracing::info!("will start at next pps");
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
fn split_gcr(buf_gcr: [u8; 8]) -> (u64, u8) {
    tracing::debug!("[gc-hw] gcr raw bytes: {:?}", buf_gcr);
    let mut buf = buf_gcr;
    buf[6] = 0;
    buf[7] = 0;
    let mut gc = u64::from_le_bytes(buf);
    gc = gc * 2 + (buf_gcr[6] & 1) as u64;
    let result = (buf_gcr[6] >> 1) & 1;
    tracing::debug!("[gc-hw] -> gc: {}, result: {}", gc, result);
    return (gc, result);
}

// format gc value before writing back to fpga; return as buf
fn gc_for_fpga(gc: u64) -> [u8; 16] {
    let gc_mod = gc / 2;
    let byte6 = gc % 2;
    let mut buf: [u8; 16] = (gc_mod as u128).to_le_bytes();
    buf[6] = byte6 as u8;
    return buf;
}

pub const BATCHSIZE: usize = 256; // max number of clicks to process in one batch

// read gcr from fpga and split gc and r
// the number of clicks read is read_length
pub fn process_gcr_stream(file: &mut File, read_length: usize) -> std::io::Result<([u64; BATCHSIZE], [u8; BATCHSIZE], usize, u128)> {

    let mut buf: [u8; BATCHSIZE * 16] = [0; BATCHSIZE * 16];

    let now = Instant::now();
    let mut len = file.read(&mut buf[..read_length*16])?;
    let elapsed_time = now.elapsed();
    if len == 0 {
        tracing::error!("[gc] len = 0");
        let len0_error = std::io::Error::new(std::io::ErrorKind::Other, "Len0");
        return Err(len0_error)
    }

    // make sure we are aligned to the 16 byte encoding of the gc
    let rest = len%16;
    if rest != 0 {
        tracing::warn!("[gc] reading gcr: length mod 16 is not zero");
        let missing_len = 16-rest;
        let check = file.read(&mut buf[len..len+missing_len])?;
        if check != missing_len {
            tracing::error!("[gc] reading gcr: could not read until mod 16");
        }
        len = len + check;
    }
    let num_clicks = len/16;
    let mut gc: [u64; BATCHSIZE] = [0; BATCHSIZE];
    let mut result: [u8; BATCHSIZE] = [0; BATCHSIZE];
    for i in 0..BATCHSIZE {
        (gc[i], result[i]) = split_gcr(buf[i * 16..i * 16 + 8].try_into().unwrap());
    }

    //println!("num clicks: {:?}", num_clicks);
    Ok((gc, result, num_clicks, elapsed_time.as_millis()))
}


// write gc back to fpga
pub fn write_gc_to_fpga(gc: [u64; BATCHSIZE], file: &mut File, num_clicks: usize) -> std::io::Result<()> {
    let mut buf: [u8; BATCHSIZE * 16] = [0; BATCHSIZE * 16];
    for i in 0..num_clicks {
        let gcbuf = gc_for_fpga(gc[i]);
        buf[i * 16..(i + 1) * 16].copy_from_slice(&gcbuf);
    }
    file.write_all(&buf[..num_clicks*16])?;
    Ok(())
}

// write gc to Alice
pub fn write_gc_to_alice(gc: [u64; BATCHSIZE], alice: &mut TcpStream, num_clicks: usize) -> std::io::Result<()> {
    let mut buf: [u8; BATCHSIZE * 8] = [0; BATCHSIZE * 8];
    for i in 0..num_clicks {
        let gcbuf = gc[i].to_le_bytes();
        buf[i * 8..(i + 1) * 8].copy_from_slice(&gcbuf);
    }
    alice.write_all(&buf[..num_clicks*8])?;
    Ok(())
}

// write gc to userfifo
pub fn write_gc_to_user(gc: [u64; BATCHSIZE], file: &mut File, num_clicks: usize) -> std::io::Result<()> {
    let mut buf: [u8; BATCHSIZE * 8] = [0; BATCHSIZE * 8];
    for i in 0..num_clicks {
        let gcbuf = gc[i].to_le_bytes();
        buf[i * 8..(i + 1) * 8].copy_from_slice(&gcbuf);
    }
    file.write_all(&buf[..num_clicks*8])?;
    Ok(())
}

// read gc coming from Bob
// similar to proces_gcr_stream
pub fn read_gc_from_bob(bob: &mut TcpStream) -> std::io::Result<([u64; BATCHSIZE], usize)> {
    let mut buf: [u8; BATCHSIZE * 8] = [0; BATCHSIZE * 8];
    let mut gc: [u64; BATCHSIZE] = [0; BATCHSIZE];

    let mut len = bob.read(&mut buf)?;

    // make sure len is aligned to the incoding
    let rest = len%8;
    if rest != 0 {
        tracing::warn!("[gc] reading gc from Bob: length mod 8 is not zero");
        let missing_len = 8-rest;
        let check = bob.read(&mut buf[len..len+missing_len])?;
        if check != missing_len {
            tracing::error!("[gc] reading gc from Bob: could not read until mod 8");
        }
        len = len + check;
    }
    
    let num_clicks = len/8;
    for i in 0..num_clicks {
        gc[i] = u64::from_le_bytes(
            buf[i * 8..(i + 1) * 8]
                .try_into()
                .expect("converting gc from bob to u64"),
        );
    }
    Ok((gc, num_clicks))
}

#[cfg(test)]
mod tests {
    use super::{HwCurrentParam, read_hw_current_int_param};

    #[test]
    fn read_decoy_delay() {
        let decoy_delay = read_hw_current_int_param(
            &HwCurrentParam::DecoyDelay.to_string(),
            "src/test_data/tmp.txt",
        );
        assert_eq!(123, decoy_delay)
    }

    #[test]
    fn read_fiber_delay() {
        let fiber_delay = read_hw_current_int_param(
            &HwCurrentParam::FiberDelay.to_string(),
            "src/test_data/tmp.txt",
        );
        assert_eq!(34, fiber_delay)
    }
}
