use clap::{Parser};
use gc::comm::{Request, Response, Comm};
use std::os::unix::net::UnixStream;
//use std::io::prelude::*;




#[derive(Parser)]
struct Cli {
    /// message to send
    #[arg(value_enum, short, long)]
    message: Request,
}


fn main() -> std::io::Result<()> {
    
    let cli = Cli::parse();

    let mut stream = UnixStream::connect("/home/vq-user/qline/startstop.s")
        .expect("could not connect to UnixStream");

    stream.send(cli.message)?;
    let m: Response = stream.recv()?;
    println!("message received {:?}", m);


    Ok(())
}






