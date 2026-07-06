//! Answering the node's readiness poll on the control socket.
//!
//! The node no longer reads the calibration flag files itself: it asks gc with
//! `Request::PollHwReady` (every 2s while idle, and at round boundaries during
//! a session). gc answers from `ready_flag_path`, which calibration (hws)
//! still manages on disk:
//!
//! - hws `start` raises the ready flag when calibration is done,
//! - hws `init` (full_init) lowers it before recalibrating and then waits for
//!   `node_idle_flag_path`, which gc raises here once the node is provably
//!   idle: the node closes all its DMA fds before polling from its idle loop,
//!   so a HwNotReady poll received while gc itself is not streaming means
//!   nothing holds the FPGA fifos anymore.

use std::io::Write;
use std::path::Path;

use comm::gc_comms::Response;
use comm::write_message;

use crate::hw::CONFIG;

/// Answer one PollHwReady request. `gc_streaming` must be true while this gc
/// instance is actively streaming (a session runs): it suppresses the
/// node-idle flag, because a poll arriving mid-session (round boundary) does
/// not mean the node's fds are closed yet.
pub fn answer_poll_hw_ready<W: Write>(stream: &mut W, gc_streaming: bool) -> std::io::Result<()> {
    let config = CONFIG.get().unwrap();
    let ready = Path::new(&config.ready_flag_path).exists();

    if ready {
        // The node is about to open its fds and run sessions: lower the idle
        // ack so the next calibration cycle's wait stays meaningful.
        match std::fs::remove_file(&config.node_idle_flag_path) {
            Ok(()) => tracing::info!(
                "hw ready: lowered node-idle flag {} (node resuming)",
                config.node_idle_flag_path
            ),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => (),
            Err(e) => tracing::error!(
                "could not remove node-idle flag {}: {e}",
                config.node_idle_flag_path
            ),
        }
        write_message(stream, Response::HwReady)
    } else {
        if !gc_streaming && !Path::new(&config.node_idle_flag_path).exists() {
            match std::fs::File::create(&config.node_idle_flag_path) {
                Ok(_) => tracing::info!(
                    "hw not ready and gc idle: raised node-idle flag {} for calibration",
                    config.node_idle_flag_path
                ),
                Err(e) => tracing::error!(
                    "could not raise node-idle flag {}: {e}",
                    config.node_idle_flag_path
                ),
            }
        }
        write_message(stream, Response::HwNotReady)
    }
}
