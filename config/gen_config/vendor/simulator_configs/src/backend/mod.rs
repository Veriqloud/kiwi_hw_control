use serde::{Deserialize, Deserializer, Serialize};

#[derive(Debug, Deserialize, Serialize, PartialEq, Clone)]
#[serde(tag = "type")]
pub enum QberConfig {
    Fixed {
        value: f64,
    },
    Uniform {
        min: f64,
        max: f64,
    },
    Gaussian {
        mean: f64,
        #[serde(rename = "std_dev")]
        std_dev: f64,
    },
}

impl Default for QberConfig {
    fn default() -> Self {
        QberConfig::Fixed { value: 0.0 }
    }
}

/// Custom deserializer for QberConfig to support both the enum format and a raw f64 (for backward compatibility).
fn deserialize_qber<'de, D>(deserializer: D) -> Result<QberConfig, D::Error>
where
    D: Deserializer<'de>,
{
    #[derive(Deserialize)]
    #[serde(untagged)]
    enum UntaggedQber {
        Fixed(f64),
        Config(QberConfig),
    }

    match UntaggedQber::deserialize(deserializer)? {
        UntaggedQber::Fixed(value) => Ok(QberConfig::Fixed { value }),
        UntaggedQber::Config(config) => Ok(config),
    }
}

#[derive(Debug, Deserialize, Serialize, PartialEq, Clone)]
pub struct DecoyStatesConfig {
    /// Mean photon number for signal pulses.
    pub mu1: f64,
    /// Mean photon number for decoy pulses.
    pub mu2: f64,
    /// Probability of selecting signal intensity mu1 (vs decoy mu2).
    pub p1: f64,
}

/// One exponential component of the detector's afterpulse hazard.
///
/// After an avalanche, charges trapped in the multiplication region are released
/// with a lifetime `tau`; each release that lands in an armed gate fires a click.
/// A single trap population therefore contributes an afterpulse rate
/// `λ(t) = (p_ap / tau) · e^(−t/tau)` per unit time after the avalanche.
///
/// Real InGaAs SPADs need more than one such population: the measured hazard of
/// the reference detector is a sum of two exponentials, a fast ~3.5 µs one and a
/// slow ~17 µs one, and it is the slow one that survives a long hold-off.
#[derive(Debug, Deserialize, Serialize, PartialEq, Clone)]
pub struct AfterpulseComponent {
    /// Detrapping time constant in seconds.
    pub tau: f64,
    /// Afterpulses this population produces per avalanche *at zero hold-off*,
    /// `p_ap = ∫₀^∞ λ(t) dt`.
    ///
    /// It is an expected number, not a probability, so values above 1 are legal
    /// (they mean the trap population would re-trigger the detector more than
    /// once if it were never blanked). The dead time suppresses it to
    /// `p_ap · e^(−dead_time/tau)`, which is what the detector actually shows —
    /// so this is the dead-time-independent way to state the parameter.
    pub p_ap: f64,
}

/// Afterpulse parameters of the reference detector: the AUREA gated InGaAs SPAD
/// characterised in `afterpulse_decoy_report.pdf`, fitted by maximum likelihood
/// on 521 471 inter-click intervals taken at 80 MHz with a 4.19 µs dead time.
///
/// At that dead time the two components contribute 0.3815 and 0.2413 afterpulses
/// per armed cycle, i.e. ~45 % of all clicks are afterpulses — a heavily
/// afterpulsing operating point, and the one the decoy analysis was done for.
pub fn reference_afterpulse() -> Vec<AfterpulseComponent> {
    vec![
        AfterpulseComponent {
            tau: 3.5183e-6,
            p_ap: 1.2543,
        },
        AfterpulseComponent {
            tau: 1.73944e-5,
            p_ap: 0.30703,
        },
    ]
}

/// Single-photon transmission of the channel.
pub const DEFAULT_ETA: f64 = 0.01;

/// Detector dead time in seconds. 10 µs is typical for a free-running InGaAs SPAD
/// and caps the sustainable count rate at 1/dead_time = 100 kcps.
pub const DEFAULT_DEAD_TIME: f64 = 10e-6;

/// Dark-count probability per gate. `1e-6` is 100 counts per second at a 10 ns
/// gate period, a typical free-running InGaAs SPAD.
pub const DEFAULT_DARK_COUNT_PROBABILITY: f64 = 1e-6;

/// Software-filter acceptance `f`: a quarter-width software gate, the typical
/// setting of the detector the model is calibrated against.
///
/// Filtering is on by default because for a heavily afterpulsing InGaAs SPAD it is
/// not optional — at its own operating point the afterpulse error floor sits above
/// the BB84 limit without it. `1.0` turns it off.
pub const DEFAULT_SOFTWARE_FILTER: f64 = 0.25;

fn default_dead_time() -> f64 {
    DEFAULT_DEAD_TIME
}

fn default_dark_count_probability() -> f64 {
    DEFAULT_DARK_COUNT_PROBABILITY
}

fn default_software_filter() -> f64 {
    DEFAULT_SOFTWARE_FILTER
}

/// Real time per simulated second. 1.0 runs in real time.
pub const DEFAULT_SPEEDUP: f64 = 1.0;

fn default_speedup() -> f64 {
    DEFAULT_SPEEDUP
}

#[derive(Debug, Deserialize, Serialize, PartialEq, Clone)]
pub struct Configuration {
    pub angles: Vec<u8>,
    pub seed: u64,
    pub eta: f64,
    #[serde(deserialize_with = "deserialize_qber")]
    pub qberr: QberConfig,
    pub pulse_distance: f64,
    /// Detector dead time in seconds. After a click the detector is blind for this
    /// long, so no two detections can be closer together and the observed count
    /// rate saturates at `1 / dead_time`. Set to `0.0` to disable.
    #[serde(default = "default_dead_time")]
    pub dead_time: f64,
    /// Dark-count probability per gate, `p_dc`. Dark counts fire independently of
    /// Alice's pulse, so they carry a random result and are the simulator's source of
    /// a non-zero vacuum yield. Set to `0.0` to disable.
    ///
    /// This is the per-gate probability the detector datasheet and the afterpulse fit
    /// both work in, not a rate: a dark count rate `D` in counts per second is
    /// `p_dc = D · pulse_distance`, so 100 cps at a 12.5 ns gate period is `1.25e-6`.
    /// Stating it per gate keeps it independent of `pulse_distance` and of `speedup`,
    /// both of which are free here — the same number describes the same detector
    /// whatever clock it is run at.
    ///
    /// Like [`Configuration::afterpulse`] it is referenced to the *full* gate; see
    /// [`Configuration::software_filter`].
    #[serde(default = "default_dark_count_probability")]
    pub dark_count_probability: f64,
    /// Software-filter acceptance `f`: the fraction of the hardware gate window the
    /// software gate keeps. Defaults to [`DEFAULT_SOFTWARE_FILTER`]; `1.0` disables
    /// filtering.
    ///
    /// The signal pulse is temporally narrow and sits inside the software gate, so
    /// every photon detection is kept. Dark counts and afterpulses are flat across
    /// the full hardware gate, so only the fraction `f` of them lands inside it and
    /// the rest are discarded — which is what divides the afterpulse and dark-count
    /// contributions to the QBER by `f`.
    ///
    /// A discarded click still fired the detector: it costs its full dead time and
    /// starts its own afterpulse tail, it is simply never reported. Filtering
    /// therefore also lowers the accepted count rate, by the acceptance probability
    /// of a click.
    ///
    /// `dark_count_probability` and [`Configuration::afterpulse`] are referenced to
    /// the *full* gate, the way they are measured, and `f` is applied to them here.
    #[serde(default = "default_software_filter")]
    pub software_filter: f64,
    /// How much faster than real time the simulation runs. `10.0` delivers in one
    /// second what the hardware would take ten seconds to produce, so a session
    /// collects ten times the counts — detections, dark counts and all.
    ///
    /// This is a pure change of clock: it is equivalent to scaling `pulse_distance`
    /// and `dead_time` down by the factor, which leaves every per-gate probability —
    /// `dark_count_probability` included — untouched. The generated data is
    /// therefore bit-identical to a real-time run of the same seed — only the
    /// wall-clock time taken to hand it over shrinks.
    ///
    /// Values below 1.0 slow the simulation down. Non-positive values are ignored.
    #[serde(default = "default_speedup")]
    pub speedup: f64,
    /// Decoy-state parameters. Absent means decoy mode is disabled.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub decoy_states: Option<DecoyStatesConfig>,
    /// Exponential components of the detector's afterpulse hazard. Empty (the
    /// default) disables afterpulsing; [`reference_afterpulse`] holds the measured
    /// parameters of the AUREA detector.
    ///
    /// Only the first [`MAX_AFTERPULSE_COMPONENTS`] entries are used.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub afterpulse: Vec<AfterpulseComponent>,
}

/// Components of the afterpulse hazard the detector model keeps.
///
/// Two is what the measured hazard needs: the fit prefers a double exponential
/// and gains only marginally from a third component. The bound is fixed so a
/// click always consumes the same number of random draws, which is what keeps
/// Alice's and Bob's streams aligned across configuration changes.
pub const MAX_AFTERPULSE_COMPONENTS: usize = 2;

impl Default for Configuration {
    fn default() -> Self {
        Self {
            angles: vec![0, 32, 64, 96],
            seed: 42,
            eta: DEFAULT_ETA,
            qberr: QberConfig::default(),
            pulse_distance: 1e-8,
            dead_time: DEFAULT_DEAD_TIME,
            dark_count_probability: DEFAULT_DARK_COUNT_PROBABILITY,
            software_filter: DEFAULT_SOFTWARE_FILTER,
            speedup: DEFAULT_SPEEDUP,
            decoy_states: Default::default(),
            afterpulse: Vec::new(),
        }
    }
}
