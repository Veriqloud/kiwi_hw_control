use clap::{Parser};
use gc::comm::{Comm, HwControl, Request, Response};
use std::io::Read;
use std::os::unix::net::UnixStream;
//use std::io::prelude::*;
use std::path::PathBuf;
use std::env::var;
use serde::Deserialize;
use std::net::TcpStream;
use std::fs;
use std::fs::{File, OpenOptions};



#[derive(Parser)]
struct Cli {
    /// message to send
    #[arg(value_enum, short, long)]
    message: Request,
}

#[derive(Deserialize, Clone, Debug)]
struct Configuration{
//    bob_gc: String,
    bob_qber: String,
}

fn recv_angles(bob: &mut TcpStream, file_angles: Option<File>) -> std::io::Result<Option<File>>{
    // reuse file descriptors if already opened earlier
    let mut file_angles = match file_angles{
        Some(fd) => {fd}
        None => {OpenOptions::new().read(true).open("/dev/xdma0_c2h_3").expect("opening /dev/xdma0_c2h_3")}
    };
    // 4x4 matrix for statistics
    let mut m0 :[[u32;4]; 4] = [[0;4]; 4];
    let mut m1 :[[u32;4]; 4] = [[0;4]; 4];

    // angles stream is 128bit = 64 angles;
    let mut aa : [u8;16] = [0; 16];
    let mut ab : [u8;16] = [0; 16];

    // result stream is 1byte = 1result;
    let mut r : [u8;64] = [0; 64];

    for _ in 0..100{
        file_angles.read_exact(&mut aa)?;
        bob.read_exact(&mut ab)?;
        bob.read_exact(&mut r)?;

        // expand angles to array
        let mut aa_expanded : [u8; 64] = [0;64];
        let mut ab_expanded : [u8; 64] = [0;64];
        for i in 0..16{
            for j in 0..4{
                aa_expanded[4*i+j] = (aa[i] & (0b11 << j*2)) >> j*2;
                ab_expanded[4*i+j] = (ab[i] & (0b11 << j*2)) >> j*2;
            }
        }
        // count cases into matrix
        for i in 0..64{
            let x = aa_expanded[i] as usize;
            let y = ab_expanded[i] as usize;
            if r[i] == 0 {
                m0[x][y] += 1;
            } else {
                m1[x][y] += 1;
            }
        }
    }
    println!("m0 {:?}", m0);
    println!("m1 {:?}", m1);
    Ok(Some(file_angles))
}

fn main() -> std::io::Result<()> {
    
//    let cli = Cli::parse();

    // send start to Alice
    let mut stream = UnixStream::connect("startstop.s").expect("could not connect to UnixStream");

    stream.send(Request::Start)?;
    let m: Response = stream.recv()?;
    println!("message received {:?}", m);


    // connect to qber_server Bob
    let mut configfile = PathBuf::from(var("CONFIGPATH").expect("os variable CONFIGPATH"));
    configfile.push("ip.json");

    let config_str = fs::read_to_string(configfile).expect("could not read config file\n");
    let config: Configuration = serde_json::from_str(&config_str).expect("JSON not well formatted\n");

    let mut bob = TcpStream::connect(config.bob_qber).expect("could not connect to stream\n");
    println!("connected to Bob");

    let mut file_angles: Option<File> = None;
    loop {
        bob.send(HwControl::SendAngles)?;
        file_angles = recv_angles(&mut bob, file_angles)?;
    }

}






