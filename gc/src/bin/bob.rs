use clap::Parser;
use gc::comm::{Comm, HwControl};
use gc::config::Configuration;
use std::str::FromStr;
use tracing_subscriber::fmt::writer::MakeWriterExt;
use uuid::Uuid;
use gc::hw::{
    init_ddr, process_gcr_stream, sync_at_pps, write_gc_to_alice, write_gc_to_fpga, write_gc_to_user, CONFIG
};
use std::fs::OpenOptions;
use std::io::prelude::*;
use std::net::{TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::time::{Instant};
use std::{thread, time};

use gc::hw::BATCHSIZE;

#[derive(Parser)]
#[command(version, about, long_about = None)]
struct Cli {
    /// Path to the configuration file
    #[arg(short = 'c', long, default_value_os_t = PathBuf::from("/home/vq-user/config/gc.json"))]
    config_path: PathBuf,
    /// Path to the log files
    #[arg(long, default_value_t = String::from("/tmp/qline_gc_logs"))]
    logs_location: String,
}



// read the gcr stream, split gcr, write gc to Alice and r to fifo
fn send_gc(alice: &mut TcpStream) -> std::io::Result<()> {
    let gcr_path = &CONFIG.get().unwrap().bob_config().fifo.gcr_file_path;
    let gcw_path = &CONFIG.get().unwrap().bob_config().fifo.gc_file_path;
    let result_path = &CONFIG.get().unwrap().bob_config().fifo.click_result_file_path;
    let gcuser_path = &CONFIG.get().unwrap().bob_config().fifo.gcuser_file_path;

    tracing::info!("[gc-bob] Opening GCR FIFO for reading: {}", gcr_path);
    let mut file_gcr = OpenOptions::new()
        .read(true)
        .open(gcr_path)
        .expect(
            format!(
                "opening {}\n",
                gcr_path
            )
            .as_str(),
        );

    tracing::info!("[gc-bob] Opening GC FIFO for writing: {}", gcw_path);
    let mut file_gcw = OpenOptions::new()
        .write(true)
        .open(gcw_path)
        .expect(
            format!(
                "opening {}\n",
                gcw_path
            )
            .as_str(),
        );

    tracing::info!("[gc-bob] Opening Click Result FIFO for writing: {}", result_path);
    let mut file_result = OpenOptions::new()
        .write(true)
        .open(result_path)
        .expect("opening result fifo\n");

    let mut option_file_gcuser = 
        if gcuser_path == ""{
            None
        } else {
            tracing::info!("[gc-bob] Opening Gcuser FIFO for writing: {}", gcuser_path);
            let file_gcuser = OpenOptions::new()
                .write(true)
                .open(gcuser_path)
                .expect("opening result fifo\n");
            Some(file_gcuser)
        };

    let mut read_length = 1;
    let mut t_loop = Instant::now();
    let mut dt_loop_max = 0;
    let mut loop_counter = 0;
    let mut total_counts = 0;
    loop {
        if loop_counter % 100 == 99{
            thread::sleep(time::Duration::from_millis(60));
        }
        let (gc, result, num_clicks, time_ms) = process_gcr_stream(&mut file_gcr, read_length)?;
        if !&CONFIG.get().unwrap().ignore_gcr_timeout{
            // keep read time between 6ms and 12ms
            // 50 ms is the limit above which a reset is requrired (debugging...)
            if (time_ms < 6) & (read_length<BATCHSIZE/2){
                read_length *= 2;
            } else if (time_ms > 12) & (time_ms < 20) & (read_length>1) {
                read_length /= 2;
            } else if time_ms >= 20{
                tracing::warn!("[gc-bob] took {:?} ms to read gcr (probably unrecoverable above 50ms)", time_ms);
                read_length = 1;
            }
            if time_ms >= 50 {
                tracing::warn!("[gc-bob] took {:?} ms to read gcr (probably unrecoverable above 50ms)", time_ms);
                let gcr_timout_error = std::io::Error::new(std::io::ErrorKind::Other, "Gcr50msTimeout");
                return Err(gcr_timout_error)
            }
        }
        write_gc_to_alice(gc, alice, num_clicks)?;
        write_gc_to_fpga(gc, &mut file_gcw, num_clicks)?;

        total_counts += num_clicks;
        if loop_counter % 100 == 0{
            println!("total counts {:?}", total_counts);
        }

        file_result.write_all(&result[..num_clicks])?;
        match option_file_gcuser.as_mut(){
            Some(file_gcuser) => {
                write_gc_to_user(gc, file_gcuser, num_clicks)?;
            },
            None => {}
        }
        let t2_loop = Instant::now();
        let dt_loop = t2_loop.duration_since(t_loop).as_millis();
        if dt_loop > dt_loop_max{
            println!("max loop time: {:?} ms", dt_loop);
            dt_loop_max = dt_loop;
        }
        t_loop = Instant::now();
        loop_counter += 1;
    }
}

fn handle_alice(alice: &mut TcpStream) -> std::io::Result<()> {
    tracing::info!("[gc-bob] Handling connection from: {}", alice.peer_addr()?);
    loop {
        match alice.recv::<HwControl>() {
            Ok(message) => {
                // The message is already printed by the comm layer
                match message {
                    HwControl::InitDdr => {
                        tracing::info!("[gc-bob] Initializing DDR...");
                        init_ddr(false);
                        tracing::info!("[gc-bob] DDR initialized.");
                    }
                    HwControl::SyncAtPps => {
                        tracing::info!("[gc-bob] Syncing at PPS and starting GC stream...");
                        sync_at_pps();
                        send_gc(alice)?;
                        tracing::info!("[gc-bob] Finished sending GC stream.");
                    } 
                }
            }
            Err(err) => {
                tracing::warn!("no message received");
                return Err(err);
            }
        }
    }
}

fn main() -> std::io::Result<()> {
    let cli = Cli::parse();

    let config: Configuration = Configuration::from_pathbuf_bob(&cli.config_path);

    CONFIG
        .set(config)
        .expect("failed to set the config global var\n");

    let log_level_filter =
        tracing_subscriber::filter::LevelFilter::from_str(&CONFIG.get().unwrap().log_level)
            .unwrap_or(tracing_subscriber::filter::LevelFilter::INFO);

    let log_id = Uuid::new_v4();
    let logfile_name = format!("gc_bob_{log_id}.log");
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
    tracing::info!("[gc-bob] Loading configuration from: {:?}", &cli.config_path);
    tracing::debug!(
        "Running with configuration: {}",
        serde_json::to_string_pretty(&CONFIG.get().unwrap())
            .unwrap_or_else(|e| format!("Failed to serialize config for logging: {}", e))
    );

    let bob_config = CONFIG.get().unwrap().bob_config();
    let click_result_path = &bob_config.fifo.click_result_file_path;
    let gcuser_path = &bob_config.fifo.gcuser_file_path;

    // delete and remake fifo file for result values
    tracing::info!("[gc-bob] Ensuring Click Result FIFO exists at: {}", click_result_path);
    std::fs::remove_file(click_result_path)
    .unwrap_or_else(|e| match e.kind() {
        std::io::ErrorKind::NotFound => (),
        _ => panic!("{}", e),
    });
    nix::unistd::mkfifo(
        Path::new(click_result_path.as_str()),
        nix::sys::stat::Mode::from_bits(0o644).unwrap(),
    )?;
    
    // delete and remake fifo file for gcuser
    if gcuser_path != "" {
        tracing::info!("[gc-bob] Ensuring GCuser FIFO exists at: {}", gcuser_path);
        std::fs::remove_file(gcuser_path)
        .unwrap_or_else(|e| match e.kind() {
            std::io::ErrorKind::NotFound => (),
            _ => panic!("{}", e),
        });
        nix::unistd::mkfifo(
            Path::new(gcuser_path.as_str()),
            nix::sys::stat::Mode::from_bits(0o644).unwrap(),
        )?;
    }


    let listen_addr = &bob_config.network.ip_gc;

    tracing::info!("[gc-bob] Attempting to bind to TCP listener at: {}", listen_addr);
    let listener =
        TcpListener::bind(listen_addr).expect("TcpListener could not bind to address\n");
    tracing::info!("[gc-bob] Successfully bound to {}", listener.local_addr().unwrap());

    loop {
        for stream in listener.incoming() {
            match stream {
                Ok(mut alice) => {
                    tracing::info!("[gc-bob] Accepted connection from: {}", alice.peer_addr()?);
                    handle_alice(&mut alice).unwrap_or_else(|e| match e.kind() {
                        std::io::ErrorKind::BrokenPipe => tracing::warn!(
                            "Broken Pipe; we are probably fine because this is how we stop"
                        ),
                        std::io::ErrorKind::Other => tracing::error!("{}", e),
                        std::io::ErrorKind::ConnectionReset => tracing::error!("{}", e),
                        _ => panic!("{}", e),
                    });
                }
                Err(err) => {
                    tracing::error!("Error: {}", err);
                    break;
                }
            }
            tracing::info!("[gc-bob] waiting for connection from Alice");
        }
    }
}
