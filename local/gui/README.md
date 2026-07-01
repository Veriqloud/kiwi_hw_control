# qline control GUI

A Tkinter + matplotlib panel to operate **qline1** and **qline2** from one window
(one tab each). It wraps the existing `local/` tools — it does not re-implement any
hardware logic.

## Run

```bash
# Self-driving mock — no hardware, no config needed. Best for a first look / demo.
python3 local/gui/qline_gui.py --demo

# Real hardware, direct IPs from config/<qline>/alice/network.json
python3 local/gui/qline_gui.py

# Real hardware over port_forwarding.sh tunnels (off-network)
python3 local/gui/qline_gui.py --use_localhost
```

`--use_localhost` only sets the initial state of each tab's connection toggle; you can
flip it per tab at runtime. `--config-root DIR` overrides where `qline1/ qline2/` live
(default: repo `config/`).

Needs Python 3, `tkinter`, and `matplotlib`. Must run where you have a display.

## What each tab shows

- **Status light**: `down` / `calibrating` / `producing key` / `error`. On error the
  message is shown on the red line below the status.
- **History plots**: count rate (from `counts_logger` via `logs.py bob tail counts`),
  key rate (`key_length / dt` from `/tmp/node_stats.csv`), and QBER (0.09 tolerance
  dashed). Data is polled every 3 s.
- **System parameters**: dead time (µs), mean photon number on Alice (photons/pulse),
  Alice–Bob distance (km). Dead time and mean photon number are adjustable (see Controls)
  and persisted in `params_<qline>.json`. Distance is **derived** from
  `hw_alice.py get --info`: `fiber_delay` (one-way fiber propagation, in 80 MHz clock
  cycles) → `distance = fiber_delay/80e6 · c/n_fiber` (n≈1.468). It only becomes known
  after a full_init (`fiber_delay` is 0 on a fresh config), and is re-read ~once a minute.

- **Loss (dB)**: total end-to-end channel loss, derived live from Alice's mean photon
  number and Bob's dead-time-corrected count rate:
  `R = clicks/0.1s`, `p = R/(g·(1−Rτ))` (g = 80 MHz pulse rate, τ = dead time),
  `T = −ln(1−p)/µ`, `loss = −10·log₁₀(T)`. Folds in detector efficiency + optics, so
  the real system reads ~20 dB at 0 fiber (µ=0.2) and more with fiber. Note: at high µ
  the detector saturates (Rτ→1) and this estimate gets noisy — keep µ≈0.2.

- **Stored keys**: Alice KMS `stored_key_count` for the Bob peer, read live from the
  ETSI QKD 014 endpoint `GET /api/v1/keys/<bob_id>/status`.

### Assumptions to verify on hardware (constants at the top of `backend.py`)

- `PULSE_RATE_HZ = 80e6`, `COUNT_WINDOW_S = 0.1` — the count register's integration
  window (matching the mon `get_counts` `×10` convention). If loss doesn't read ~20 dB
  at 0 fiber with µ=0.2, this window is the first thing to check.
- `FIBER_GROUP_INDEX = 1.468` — for the distance conversion.
- µ defaults to **0.2** (the vca currently sets it implicitly; treated as 0.2 until set
  explicitly via the mean-photon control).
## Controls

| Button | Runs |
|---|---|
| Wake & Produce | `run_qkd.sh <qline> --init` (Wake-on-LAN → bring-up → start key production) |
| Full Init | `hws.py --full_init` (re-calibrate a running system; key prod pauses) |
| Auto-tune | `hws.py --auto_control` (re-tune to lower QBER) |
| Shutdown | `shutdown.py both --yes` (power off both nodes via restartd; confirm dialog) |
| Dead time (µs) → Set | `hw_bob.py set --spd_deadtime <µs>` (detector dead time; ~15 gated / 50 freerunning) |
| Mean photon # → Set, mode **photons/pulse** | `hw_alice.py set --photons <N>` (direct, 0.003–3) |
| Mean photon # → Set, mode **target counts** | `hws.py --command find_vca_<N>` (drive Alice VCA to N detector counts) |

Action output streams into the log pane at the bottom.

## Status derivation (real backend)

- **down** — `logs.py alice stats` unreachable.
- **error** — latest `counts.log` line is an `ALERT` (detector dark / FPGA stopped).
- **producing key** — newest `node_stats.csv` round is < 150 s old.
- **calibrating** — reachable but no fresh rounds (mid-calibration or idle).

Which exact conditions map to `error` is intentionally minimal for now and easy to
extend in `backend.py:RealBackend.refresh`.

## Notes / limits

- **Wake & Produce** goes through `run_qkd.sh`, which SSHes to the `KAlice`/`KBob`
  host aliases and needs L2 for Wake-on-LAN — so it works from the on-network control
  host, not over `--use_localhost` port forwarding.
- Architecture: `backend.py` holds `RealBackend` (shells out to the tools) and
  `DemoBackend` (mock) behind one interface; `qline_gui.py` is pure UI and never calls
  the tools directly.
