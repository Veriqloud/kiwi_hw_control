use clap::Parser;
use comm::{
    gc_comms::{Request, Response},
    read_message, write_message,
};
use std::{os::unix::net::UnixStream, str::FromStr};
use std::path::PathBuf;

#[derive(Parser)]
struct Cli {
    // message to send
    #[arg(short, long, value_parser = Request::from_str)]
    message: Request,
    #[arg(short, default_value_os_t = PathBuf::from("/home/vq-user/start_stop.socket"))]
    pub command_socket_path: PathBuf,
}

fn main() -> std::io::Result<()> {
    let cli = Cli::parse();

    let mut stream = UnixStream::connect(&cli.command_socket_path)
        .expect("could not connect to UnixStream");

    write_message(&mut stream, cli.message)?;

    let m: Response = read_message(&mut stream)?;
    println!("message received {:?}", m);

    Ok(())
}
