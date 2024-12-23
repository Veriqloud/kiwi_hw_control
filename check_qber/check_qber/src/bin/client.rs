use clap::{Parser, Subcommand};
use std::fs;
use std::fs::File;
use serde::Deserialize;
use check_qber::{Message, MessageHeader, rcv, read_angles, calc_qber};
//use std::{thread, time};


#[derive(Deserialize, Debug)]
struct Configuration{
    ip_address: String
}


#[derive(Parser)]
struct Cli {
    #[command(subcommand)]
    command: Option<Commands>,
    /// How many chunks to read? One chunk are 64 angles.
    chunks: u32,
    /// repeat qber calculation this many times
    repeat: u32,
}

#[derive(Subcommand)]
enum Commands {
    /// Print the status of the qline
    Status,
    Init
}




fn main() -> std::io::Result<()> {

    let cli = Cli::parse();

    let config_str = fs::read_to_string("config.json")
        .expect("could not read config file\n");
    let config: Configuration = serde_json::from_str(&config_str)
        .expect("JSON not well formatted\n");


    let mut stream = std::net::TcpStream::connect(config.ip_address)
        .expect("could not connect to stream\n");

    let mut fifo = File::open("fifo1")
        .expect("could not open fifo1");

    // loop calculating qber
    for _i in 0..cli.repeat {
        let m = Message{
            header : MessageHeader::Start,
            body : vec![cli.chunks],
        };
        m.snd(&mut stream);

        let angles = read_angles(&mut fifo, cli.chunks as usize)
            .expect("could not read angles from fifo");

        let mr = rcv(&mut stream).expect("error receiving angles from Bob");

        let qber = calc_qber(angles, mr.body);

        println!("qber {:?}", qber);
    }

    // tell server we are done
    let m = Message{
        header : MessageHeader::Done,
        body : vec![0],
    };
    m.snd(&mut stream);


    


    Ok(())
}
