use clap::{Parser};
use gc::ControlMessage;
use std::os::unix::net::UnixStream;
use std::io::prelude::*;




#[derive(Parser)]
struct Cli {
    /// message to send
    #[arg(value_enum, short, long)]
    message: ControlMessage,
}


fn main() -> std::io::Result<()> {
    
    let cli = Cli::parse();

    let mut stream = UnixStream::connect("startstop.s")
        .expect("could not connect to UnixStream");

    let m_b = cli.message  as u8;

    let _ = stream.write(&[m_b]);


    Ok(())
}






