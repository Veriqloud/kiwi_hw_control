use clap::Parser;
use comm::gc_comms::{Request, Response};
use comm::{read_message, write_message};
use gc::comm::{Comm, HwControl};
use gc::config::Configuration;
use gc::hw::{CONFIG, init_ddr, read_gc_from_bob, sync_at_pps, wait_for_pps, write_gc_to_fpga};
use std::fs::OpenOptions;
use std::io::Write;
use std::net::TcpStream;
use std::os::unix::net::UnixListener;
use std::path::PathBuf;
use std::str::FromStr;
use std::sync::mpsc::{Receiver, Sender, TryRecvError, channel};
use std::{thread, time};
use tracing_subscriber::fmt::writer::MakeWriterExt;
use uuid::Uuid;

#[derive(Parser)]
struct Cli {
    ///// number of gc to process before stop
    //num: u64,
    /// save result to file
    #[arg(short, long)]
    save: bool,

    /// Path to the configuration file
    #[arg(short = 'c', long, default_value_os_t = PathBuf::from("/home/vq-user/config/gc.json"))]
    config_path: PathBuf,
    /// Path to the log files
    #[arg(long, default_value_t = String::from("/tmp/qline_gc_logs"))]
    logs_location: String,
}

fn recv_gc(bob: &mut TcpStream, rx: &Receiver<Request>, debug_mode: bool) -> std::io::Result<()> {
    let mut file_gcw = OpenOptions::new()
        .write(true)
        .open(&CONFIG.get().unwrap().alice_config().fifo.gc_file_path)
        .expect(
            format!(
                "opening {}\n",
                &CONFIG.get().unwrap().alice_config().fifo.gc_file_path
            )
            .as_str(),
        );

    tracing::debug!(debug_mode = ?debug_mode);

    loop {
        let mut vgc: Vec<u64> = Vec::new();

        for i in 0..100 {
            let gc = read_gc_from_bob(bob)?;
            write_gc_to_fpga(gc, &mut file_gcw)?;

            if debug_mode {
                vgc.extend_from_slice(&gc);
            }

            if (i % 1000) == 0 {
                tracing::debug!("gc[0]: {}", gc[0]);
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
        if debug_mode {
            let mut file_gc_debug = OpenOptions::new()
                .create(true)
                .append(true)
                .open("gc.txt")
                .expect("opening gc.txt\n");
            let strings: Vec<String> = vgc.iter().map(|n| n.to_string()).collect();
            writeln!(file_gc_debug, "{}", strings.join("\n"))?;
        }
    }
    //thread::sleep(time::Duration::from_millis(100));
}

fn connect_to_bob(ip_bob: &str) -> TcpStream {
    // loop until bob opens TcpStream
    loop {
        match TcpStream::connect(&ip_bob){
            Ok(stream) => {
                return stream
            },
            Err(e) => {
                match e.kind() {
                    std::io::ErrorKind::ConnectionRefused => {
                        thread::sleep(time::Duration::from_millis(1000));
                        continue
                    },
                    _ => {
                        println!("connect_to_bob ERROR: {}\nexiting program!", e);
                        std::process::exit(1);
                    },
                }
            }
        }
    }
}

fn handle_bob(rx: Receiver<Request>, tx: Sender<Response>, ip_bob: &str) {
    tracing::info!("connecting to Bob...");
    let mut bob =  connect_to_bob(&ip_bob);
    tracing::info!("connected to Bob");
    let mut debug_mode = false;

    loop {
        match rx.recv().unwrap() {
            Request::DebugOn => {
                debug_mode = true;
                // remove gc.txt if it exists
                std::fs::remove_file("gc.txt").unwrap_or_else(|e| match e.kind() {
                    std::io::ErrorKind::NotFound => (),
                    _ => panic!("{}", e),
                });
                tx.send(Response::Done)
                    .expect("sending message through c2\n");
            }
            Request::Start => {
                bob.send(HwControl::InitDdr).expect("sending to Bob\n");
                init_ddr(true);
                tx.send(Response::Done)
                    .expect("sending message through c2\n");
                wait_for_pps();
                bob.send(HwControl::SyncAtPps).expect("sending to Bob\n");
                sync_at_pps();
                tracing::info!("files opened");
                // loop until Stop
                match recv_gc(&mut bob, &rx, debug_mode) {
                    Ok(()) => {
                        tx.send(Response::Done)
                            .expect("sending message through c2\n");
                        bob = TcpStream::connect(&ip_bob).expect("could not connect to stream\n");
                        continue;
                    }
                    Err(e) => match e.kind() {
                        std::io::ErrorKind::UnexpectedEof => {
                            tracing::warn!("Unexpected Eof; reconnecting to Bob");
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
                    .expect("sending message through c2\n");
            }
        }
    }
}

fn handle_control(tx: Sender<Request>, rx: Receiver<Response>) {
    // remove unix socket if it exists
    std::fs::remove_file(
        CONFIG
            .get()
            .unwrap()
            .alice_config()
            .fifo
            .command_socket_path,
    )
    .unwrap_or_else(|e| match e.kind() {
        std::io::ErrorKind::NotFound => (),
        _ => panic!("{}", e),
    });

    let listener = UnixListener::bind(
        CONFIG
            .get()
            .unwrap()
            .alice_config()
            .fifo
            .command_socket_path,
    )
    .expect("UnixListener could not bind to address\n");

    for stream in listener.incoming() {
        match stream {
            Ok(mut stream) => {
                let message: Request = read_message(&mut stream).expect("recv\n");
                tx.send(message)
                    .expect("sending message through  channel\n");
                let m = rx.recv().unwrap();
                write_message(&mut stream, m).expect("sending message\n");
            }
            Err(err) => {
                tracing::error!("Error: {}", err);
                break;
            }
        }
    }
}

fn main() -> std::io::Result<()> {
    let cli = Cli::parse();

    let config: Configuration = Configuration::from_pathbuf_alice(&cli.config_path);

    CONFIG
        .set(config)
        .expect("failed to set the config global var\n");

    let log_level_filter =
        tracing_subscriber::filter::LevelFilter::from_str(&CONFIG.get().unwrap().log_level)
            .unwrap_or(tracing_subscriber::filter::LevelFilter::INFO);

    let log_id = Uuid::new_v4();
    let logfile_name = format!("gc_alice_{log_id}.log");
    let logfile_appender = tracing_appender::rolling::daily(&cli.logs_location, &logfile_name);
    let stdout_level = log_level_filter
        .into_level()
        .unwrap_or(tracing::Level::INFO);
    let stdout_writer = std::io::stdout.with_max_level(stdout_level);

    tracing_subscriber::fmt()
        .with_max_level(log_level_filter)
        .with_writer(stdout_writer.and(logfile_appender))
        .init();

    tracing::info!(
        "Logging initialized with level {:?} to stdout and file {}",
        stdout_level,
        format!("{}/{}", &cli.logs_location, &logfile_name)
    );
    tracing::info!("Loading configuration from: {:?}", &cli.config_path);
    tracing::debug!(
        "Running with configuration: {}",
        serde_json::to_string_pretty(&CONFIG.get().unwrap())
            .unwrap_or_else(|e| format!("Failed to serialize config for logging: {}", e))
    );

    loop {
        let (c1_tx, c1_rx) = channel();
        let (c2_tx, c2_rx) = channel();
        let thread_join_handle = thread::spawn(move || {
            handle_bob(
                c1_rx,
                c2_tx,
                &CONFIG.get().unwrap().alice_config().network.ip_gc,
            )
        });

        handle_control(c1_tx, c2_rx);

        thread_join_handle.join().expect("joining thread\n");
    }
}
