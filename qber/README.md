This program calculates and prints the qubit error rate (qber).


# Installation

```.bash
cargo build --release
cp target/release/alice ~/bin/qber_alice
cp target/release/bob ~/bin/qber_bob
```

# Running hw_sim + gc + qber

Please see the readme of `gc`. 

# Running on the hardware

We assume the hardware is properly setup and calibrated. That means that `gc` is running.

On Bob 

```.bash
cd ~/server/
qber
```


On Alice

```.bash
qber 6400
```








