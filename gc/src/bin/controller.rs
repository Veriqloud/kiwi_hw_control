use clap::Parser;
use comm::{
    gc_comms::{Request, Response},
    read_message, write_message,
};
use std::{os::unix::net::UnixStream};
use std::path::PathBuf;
use std::{thread, time};

#[derive(Parser)]
struct Cli {
    // message to send
    #[arg(short, long)]
    time: u64,
    #[arg(short, default_value_os_t = PathBuf::from("/tmp/gc_startstop"))]
    pub command_socket_path: PathBuf,
}

fn main() -> std::io::Result<()> {
    let cli = Cli::parse();

    let mut stream = UnixStream::connect(&cli.command_socket_path)
        .expect("could not connect to UnixStream");

    write_message(&mut stream, Request::Start)?;
    thread::sleep(time::Duration::from_secs(cli.time));
    write_message(&mut stream, Request::Stop)?;

    let m: Response = read_message(&mut stream)?;
    println!("message received {:?}", m);

    Ok(())
}
