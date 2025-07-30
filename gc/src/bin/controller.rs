use clap::Parser;
use comm::{
    gc_comms::{Request, Response},
    read_message, write_message,
};
use std::{os::unix::net::UnixStream, str::FromStr};

#[derive(Parser)]
struct Cli {
    // message to send
    #[arg(short, long, value_parser = Request::from_str)]
    message: Request,
}

fn main() -> std::io::Result<()> {
    let cli = Cli::parse();

    let mut stream = UnixStream::connect("/home/vq-user/start_stop.socket")
        .expect("could not connect to UnixStream");

    write_message(&mut stream, cli.message)?;

    let m: Response = read_message(&mut stream)?;
    println!("message received {:?}", m);

    Ok(())
}
