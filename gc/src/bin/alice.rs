use clap::Parser;
use comm::gc_comms::{Request, Response};
use comm::{read_message, write_message};
use gc::comm::{Comm, HwControl};
use gc::config::ConfigNetworkAlice;
use gc::hw::{init_ddr, read_gc_from_bob, sync_at_pps, wait_for_pps, write_gc_to_fpga};
use std::fs::OpenOptions;
use std::io::Write;
use std::net::TcpStream;
use std::os::unix::net::UnixListener;
use std::sync::mpsc::{Receiver, Sender, TryRecvError, channel};
use std::thread;

#[derive(Parser)]
struct Cli {
    /// number of gc to process before stop
    num: u64,
    /// save result to file
    #[arg(short, long)]
    save: bool,
}

fn recv_gc(bob: &mut TcpStream, rx: &Receiver<Request>, debug: bool) -> std::io::Result<()> {
    let mut file_gcw = OpenOptions::new()
        .write(true)
        .open("/dev/xdma0_h2c_0")
        .expect("opening /dev/xdma0_h2c_0");

    println!("DEBUG: {:?}", debug);

    loop {
        let mut vgc: Vec<u64> = Vec::new();

        for i in 0..100 {
            let gc = read_gc_from_bob(bob)?;
            write_gc_to_fpga(gc, &mut file_gcw)?;

            if debug {
                vgc.extend_from_slice(&gc);
            }

            if (i % 1000) == 0 {
                println!("{:?}", gc[0]);
            };
        }
        match rx.try_recv() {
            Ok(m) => match m {
                Request::Stop => {
                    //tx.send(Response::Done).expect("sending message through c2");
                    return Ok(());
                }
                _ => {}
            },
            Err(e) => match e {
                TryRecvError::Empty => {}
                TryRecvError::Disconnected => panic!("rx channel disconnected"),
            },
        }
        if debug {
            let mut file_gc_debug = OpenOptions::new()
                .create(true)
                .append(true)
                .open("gc.txt")
                .expect("opening gc.txt");
            let strings: Vec<String> = vgc.iter().map(|n| n.to_string()).collect();
            writeln!(file_gc_debug, "{}", strings.join("\n"))?;
            //return Ok(())
        }
    }
    //thread::sleep(time::Duration::from_millis(100));
}

fn handle_bob(rx: Receiver<Request>, tx: Sender<Response>, ip_bob: String) {
    let mut bob = TcpStream::connect(&ip_bob).expect("could not connect to stream\n");
    println!("connected to Bob");

    let mut debug = false;

    loop {
        match rx.recv().unwrap() {
            Request::DebugOn => {
                debug = true;
                // remove gc.txt if it exists
                std::fs::remove_file("gc.txt").unwrap_or_else(|e| match e.kind() {
                    std::io::ErrorKind::NotFound => (),
                    _ => panic!("{}", e),
                });
                tx.send(Response::Done).expect("sending message through c2");
            }
            Request::Start => {
                bob.send(HwControl::InitDdr).expect("sending to Bob");
                init_ddr(true);
                tx.send(Response::Done).expect("sending message through c2");
                wait_for_pps();
                bob.send(HwControl::SyncAtPps).expect("sending to Bob");
                sync_at_pps();
                println!("files opened");
                // loop until Stop
                match recv_gc(&mut bob, &rx, debug) {
                    Ok(()) => {
                        tx.send(Response::Done).expect("sending message through c2");
                        bob = TcpStream::connect(&ip_bob).expect("could not connect to stream\n");
                        continue;
                    }
                    Err(e) => match e.kind() {
                        std::io::ErrorKind::UnexpectedEof => {
                            println!("Warning: Unexpected Eof; reconnecting to Bob");
                            bob =
                                TcpStream::connect(&ip_bob).expect("could not connect to stream\n");
                            continue;
                        }
                        _ => panic!("interaction with bob {}", e),
                    },
                }
            }
            _ => {
                tx.send(Response::DidNothing)
                    .expect("sending message through c2");
            }
        }
    }
}

fn handle_control(tx: Sender<Request>, rx: Receiver<Response>) {
    // remove unix socket if it exists
    std::fs::remove_file("/home/vq-user/qline/startstop.s").unwrap_or_else(|e| match e.kind() {
        std::io::ErrorKind::NotFound => (),
        _ => panic!("{}", e),
    });

    let listener = UnixListener::bind("/home/vq-user/qline/startstop.s")
        .expect("UnixListener could not bind to address\n");

    for stream in listener.incoming() {
        match stream {
            Ok(mut stream) => {
                let message: Request = read_message(&mut stream).expect("recv");
                tx.send(message).expect("sending message through  channel");
                let m = rx.recv().unwrap();
                write_message(&mut stream, m).expect("sending message");
            }
            Err(err) => {
                println!("Error: {}", err);
                break;
            }
        }
    }
}

fn main() -> std::io::Result<()> {
    loop {
        let network =
            ConfigNetworkAlice::from_path("/home/vq-user/qline/config/network.json".into());

        let (c1_tx, c1_rx) = channel();
        let (c2_tx, c2_rx) = channel();
        let thread_join_handle = thread::spawn(move || handle_bob(c1_rx, c2_tx, network.ip_bob_gc));
        handle_control(c1_tx, c2_rx);

        thread_join_handle.join().expect("joining thread");
    }
}
