use comm::gc_comms::*;
use comm::qber_comms::*;

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use clap::Parser;
use comm::read_message;
use comm::write_message;
use std::fmt;
use std::fs::{File, OpenOptions};
use std::io::Read;
use std::io::Write;
use std::net::TcpStream;
use std::os::unix::net::UnixStream;
use std::path::PathBuf;

use std::time::Instant;

use qber::config::AliceConfig;


#[derive(Parser, Debug)]
struct Cli {
    /// number of clicks to average over
    num: u32,
    /// Save files for debug
    #[arg(short, long)]
    debug: bool,
    /// Provide a config file for the fifos.
    #[arg(short, default_value_os_t = PathBuf::from("/home/vq-user/config/qber.json"))]
    pub config_path: PathBuf,
    /// Provide a config file for the network.
    #[arg(short, default_value = "/home/vq-user/config/network.json")]
    pub network_path: String,
}

// for printing the matrix nicely
struct QberMatrix([[f64; 4]; 4]);

impl fmt::Display for QberMatrix {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        let m = self.0;
        write!(
            f,
            "{:>6.3}  {:>6.3}  {:>6.3}  {:>6.3}
{:>6.3}  {:>6.3}  {:>6.3}  {:>6.3}
{:>6.3}  {:>6.3}  {:>6.3}  {:>6.3}
{:>6.3}  {:>6.3}  {:>6.3}  {:>6.3}",
            m[0][0],
            m[0][1],
            m[0][2],
            m[0][3],
            m[1][0],
            m[1][1],
            m[1][2],
            m[1][3],
            m[2][0],
            m[2][1],
            m[2][2],
            m[2][3],
            m[3][0],
            m[3][1],
            m[3][2],
            m[3][3]
        )
    }
}

// for printing angles to file
struct Line([u8; 3]);

impl fmt::Display for Line {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        let l = self.0;
        write!(f, "{:}\t{:}\t{:}", l[0], l[1], l[2])
    }
}

fn recv_angles(
    bob: &mut TcpStream,
    config: &AliceConfig,
    num: u32,
    file_angles: Option<File>,
    debug: bool,
) -> std::io::Result<Option<File>> {
    // reuse file descriptors if already opened earlier
    let mut file_angles = match file_angles {
        Some(fd) => fd,
        None => {
            OpenOptions::new()
                .read(true)
                .open(&config.angle_file_path)
                .expect("opening angle file")
        }
    };
    let now = Instant::now();

    // 4x4 matrix for statistics
    let mut m0: [[u32; 4]; 4] = [[0; 4]; 4];
    let mut m1: [[u32; 4]; 4] = [[0; 4]; 4];

    // angles stream is 128bit = 32 angles;
    let mut aa: [u8; 16] = [0; 16];
    let mut ab: [u8; 16] = [0; 16];

    // result stream is 1byte = 1result;
    let mut r: [u8; 32] = [0; 32];

    // save vector for debug: angle_alice, angle_bob, result
    let mut vdebug: Vec<[u8; 3]> = Vec::new();

    //println!("[qber-alice] Telling qber-bob we want {} clicks.", num);
    bob.write_all(&num.to_le_bytes())?;

    for _ in 0..num / 32 {
        file_angles.read_exact(&mut aa)?;
        bob.read_exact(&mut ab)?;

        bob.read_exact(&mut r)?;

        // expand angles to array
        let mut aa_expanded: [u8; 32] = [0; 32];
        let mut ab_expanded: [u8; 32] = [0; 32];
        for i in 0..16 {
            for j in 0..2 {
                aa_expanded[2 * i + j] = (aa[i] & (0b11 << j * 4)) >> j * 4;
                ab_expanded[2 * i + j] = (ab[i] & (0b11 << j * 4)) >> j * 4;
            }
        }
        for i in 0..32 {
            if debug {
                vdebug.push([aa_expanded[i], ab_expanded[i], r[i]]);
            }
            let x = aa_expanded[i] as usize;
            let y = ab_expanded[i] as usize;
            if r[i] == 0 {
                m0[x][y] += 1;
            } else {
                m1[x][y] += 1;
            }
        }
    }
    let mut mdiv: [[f64; 4]; 4] = [[0.; 4]; 4];
    for i in 0..4 {
        for j in 0..4 {
            if m1[i][j] == 0 {
                mdiv[i][j] = -1.;
            } else {
                mdiv[i][j] = m0[i][j] as f64 / m1[i][j] as f64;
            }
        }
    }

    let qber_alice =
        (m0[1][0] + m1[2][0]) as f64 / (m0[1][0] + m1[1][0] + m0[2][0] + m1[2][0]) as f64;
    let qber_bob =
        (m0[0][1] + m1[0][2]) as f64 / (m0[0][1] + m1[0][1] + m0[0][2] + m1[0][2]) as f64;
    let qber = (m0[1][0] + m1[2][0] + m0[0][1] + m1[0][2]) as f64
        / (m0[1][0] + m1[1][0] + m0[2][0] + m1[2][0] + m0[0][1] + m1[0][1] + m0[0][2] + m1[0][2])
            as f64;

    let elapsed_time = now.elapsed();
    let counts  = (num / 32) * 32;

    println!(
        "counts: {:} ({:6.0} counts/s )
{:}",
        counts, counts as f64 /elapsed_time.as_secs_f64(),
        QberMatrix(mdiv)
    );
    println!(
        "qber (alice, bob, total): {:>6.2}  {:>6.2}  {:>6.2}
",
        qber_alice * 100.,
        qber_bob * 100.,
        qber * 100.
    );
    if debug {
        let mut file_debug = OpenOptions::new()
            .create(true)
            .append(true)
            .open("angles.txt")
            .expect("opening angles.txt");
        let strings: Vec<String> = vdebug.iter().map(|&n| Line(n).to_string()).collect();
        writeln!(file_debug, "{}", strings.join("\n"))?;
    }
    Ok(Some(file_angles))
}

fn main() -> std::io::Result<()> {
    let cli = Cli::parse();
    let config = AliceConfig::from_pathbuf(&cli.config_path);
    let mut bob =
        TcpStream::connect(&config.ip_bob).expect("connecting to Bob_qber via TcpStream\n");

    let mut debug = false;
    if cli.debug {
        debug = true;
        // remove angles.txt if it exists
        std::fs::remove_file("angles.txt").unwrap_or_else(|e| match e.kind() {
            std::io::ErrorKind::NotFound => (),
            _ => panic!("{}", e),
        });

        let mut stream = UnixStream::connect(&config.command_socket_path)
            .expect("could not connect to UnixStream");
        write_message(&mut stream, Request::DebugOn)?;
        let _m: Response = read_message(&mut stream)?;
    }

    let mut stream = UnixStream::connect(&config.command_socket_path).expect(&format!(
        "could not connect to UnixStream {:?}",
        &config.command_socket_path
    ));

    // catch ctl-c to send stop before exiting
    let stop = Arc::new(AtomicBool::new(false));
    let stop_clone = stop.clone();

    ctrlc::set_handler(move || {
        stop_clone.store(true, Ordering::SeqCst);
    }).expect("Error setting Ctrl-C handler");


    write_message(&mut stream, Request::Start)?;
    let _m: Response = read_message(&mut stream)?;

    let mut file_angles: Option<File> = None;
    loop {
        write_message(&mut bob, &Qber::SendAngles)?;
        file_angles = recv_angles(&mut bob, &config, cli.num, file_angles, debug)?;
        if stop.load(Ordering::SeqCst) { break }
    }

    Ok(())
}








