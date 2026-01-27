use clap::Parser;
use comm::gc_comms::{Request, Response};
use comm::{read_message, write_message};
use gc::comm::{Comm, HwControl};
use gc::config::Configuration;
use gc::hw::{BATCHSIZE, CONFIG, decompose_num_clicks, init_ddr, read_gc_from_bob, sync_at_pps, wait_for_pps, write_gc_to_fpga};
use std::fs::OpenOptions;
//use std::io::Write;
use std::net::TcpStream;
use std::os::unix::net::UnixListener;
use std::path::PathBuf;
use std::str::FromStr;
//use std::sync::mpsc::{Receiver, Sender, TryRecvError, channel};
use std::{thread, time};
use tracing_subscriber::fmt::writer::MakeWriterExt;
use uuid::Uuid;
use std::time::{Instant};

use std::sync::Mutex;


// for stopping threads
static RUNNING: Mutex<bool> = Mutex::new(false);

#[derive(Parser)]
#[command(version, about, long_about = None)]
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

// receive gc from Bob until STOP
fn recv_gc(bob: &mut TcpStream) -> std::io::Result<()> {
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
    tracing::info!("[gc-alice] gcw file opened");


    let mut t_loop = Instant::now();
    let mut dt_loop_max = 0;
    tracing::info!("[gc-alice] reading gc from Bob");
    while *RUNNING.lock().unwrap() {
        let now = Instant::now();
        //thread::sleep(time::Duration::from_millis(20));
        let (gc, num_clicks) = read_gc_from_bob(bob)?;
        let t_read_gc = now.elapsed().as_millis();
        if t_read_gc > 20 {
            tracing::warn!("[gc-alice] took {:?} ms to get {:?} gcs from Bob", t_read_gc, num_clicks);
        }
        if num_clicks == 0 {
            if CONFIG.get().unwrap().ignore_gcr_timeout {
                continue
            } else {
                panic!("got 0 clicks from Bob (timeout)")
            }
        } else {
            // make sure the number of written gcs is a power of 2 and less than BATCHSIZE
            let num_clicks_array = decompose_num_clicks(num_clicks);
            let mut pos = 0;
            for num in num_clicks_array{
                let mut gc_tmp = [0; BATCHSIZE];
                gc_tmp[0..num].copy_from_slice(&gc[pos..pos+num]);
                pos = pos + num;
                write_gc_to_fpga(gc_tmp, &mut file_gcw, num)?;
            }
        }
        let t2_loop = Instant::now();
        let dt_loop = t2_loop.duration_since(t_loop).as_millis();
        if dt_loop > dt_loop_max{
            println!("max loop time: {:?} ms; num clicks: {:?}", dt_loop, num_clicks);
            dt_loop_max = dt_loop;
        }
        t_loop = Instant::now();

    }
    tracing::info!("[gc-alice] stopped reading gc from Bob");
    Ok(())
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


// create socket for start/stop commands from controller
fn create_control_socket() -> UnixListener {
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
    // create unix socket
    let listener = UnixListener::bind(
        CONFIG
            .get()
            .unwrap()
            .alice_config()
            .fifo
            .command_socket_path,
    )
    .expect("UnixListener could not bind to address\n");
    return listener;
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
        "[gc-alice] Logging initialized with level {:?} to stdout and file {}",
        stdout_level,
        format!("{}/{}", &cli.logs_location, &logfile_name)
    );
    tracing::info!("[gc-alice] Loading configuration from: {:?}", &cli.config_path);
    tracing::debug!(
        "[gc-alice] Running with configuration: {}",
        serde_json::to_string_pretty(&CONFIG.get().unwrap())
            .unwrap_or_else(|e| format!("Failed to serialize config for logging: {}", e))
    );

    loop {
        *RUNNING.lock().unwrap() = false;
        let control_socket = create_control_socket();
        tracing::info!("[gc-alice] control socket created");

        for stream in control_socket.incoming() {
            let mut bob = connect_to_bob(&CONFIG.get().unwrap().alice_config().network.ip_gc);
            match stream {
                Ok(mut stream) => {
                    let message: Request = read_message(&mut stream).expect("recv\n");

                    // wait for start message
                    match message {
                        Request::Start => {
                            tracing::info!("[gc-alice] got start message");
                            // init Alice and Bob
                            bob.send(HwControl::InitDdr).expect("sending to Bob\n");
                            init_ddr(true);
                            write_message(&mut stream, Response::Done)
                                .expect("sending message through control socket");
                            wait_for_pps();
                            bob.send(HwControl::SyncAtPps).expect("sending to Bob\n");
                            sync_at_pps();
                        }
                        _ => {
                            write_message(&mut stream, Response::DidNothing)
                                .expect("sending message through control socket");
                        }
                    }
                    // receive gc in a separate thread
                    *RUNNING.lock().unwrap() = true;
                    let thread_join_handle = 
                        thread::Builder::new().name("recv_gc".to_string()).spawn(move || {
                        recv_gc(&mut bob).expect("recv_gc returned an error");
                    }).expect("building thread");

                    // wait for stop message
                    println!("waiting for message");

                    match read_message(&mut stream) {
                        Ok(message) => {
                            match message {
                                Request::Stop => {
                                    tracing::info!("[gc-alice] got stop message");
                                    *RUNNING.lock().unwrap() = false;
                                    write_message(&mut stream, Response::Done)
                                        .expect("sending message through control socket");
                                }
                                _ => {
                                    write_message(&mut stream, Response::DidNothing)
                                        .expect("sending message through control socket");
                                }
                            }
                        }
                        // recover from Eof error due to disconnected controller
                        Err(e) => {
                            match e.kind() {
                                std::io::ErrorKind::UnexpectedEof => {
                                    // terminate thread recv_gc
                                    *RUNNING.lock().unwrap() = false;
                                    thread::sleep(time::Duration::from_millis(100));
                                    break
                                }
                                _ => panic!("{}", e)
                            }
                        }
                    }

                    // finish
                    thread_join_handle.join().expect("thread join handle");

                }
                Err(err) => {
                    tracing::error!("[gc-alice] Error: {}", err);
                    break;
                }
            }
            tracing::info!("[gc-alice] waiting for message on control socket");
        }

    }
}






