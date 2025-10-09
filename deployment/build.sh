#!/bin/bash

# this is a helper for updating and building the software stack



# location of the repos
hw_sim=../../hw_sim
qline_backend=../../qline_backend
bin=~/bin

blue='\033[0;36m'
yellow='\033[0;33m'
NC='\033[0m' # No Color

usage() {
    echo "Usage: $0 {pull|build|install|all}"
    exit 1
}

warning_nonmaster_branch(){
    if [ $(git branch --show-current) != "master" ]; then
        printf "${yellow}warning: you are not on master branch${NC}\n"
    fi
}

pull(){
    printf "${blue}pulling kiwi_hw_control...${NC}\n"
    warning_nonmaster_branch
    git pull

    printf "${blue}pulling hw_sim...${NC}\n"
    cd $hw_sim
    warning_nonmaster_branch
    git pull
    cd $OLDPWD

    printf "${blue}pulling qline_backend...${NC}\n"
    cd $qline_backend
    warning_nonmaster_branch
    git pull
    cd $OLDPWD
}

build(){
    cd ../gc
    printf "${blue}building gc...${NC}\n"
    cargo build --release
    cd $OLDPWD

    printf "${blue}building qber...${NC}\n"
    cd ../qber
    cargo build --release
    cd $OLDPWD

    printf "${blue}building gen_config...${NC}\n"
    cd ../config/gen_config
    cargo build --release
    cd $OLDPWD
    
    printf "${blue}building hw_sim...${NC}\n"
    cd $hw_sim
    cargo build --release
    cd $OLDPWD
    
    printf "${blue}building node...${NC}\n"
    cd $qline_backend/node
    cargo build --release
    cd $OLDPWD
    
    printf "${blue}building kms...${NC}\n"
    cd $qline_backend/kms
    cargo build --release
    cd $OLDPWD
}

install(){
    printf "${blue}installing...${NC}\n"

    cp -v ../gc/target/release/alice $bin/gc_alice
    cp -v ../gc/target/release/bob $bin/gc_bob
    
    cp -v ../qber/target/release/alice $bin/qber_alice
    cp -v ../qber/target/release/bob $bin/qber_bob
    
    cp -v ../config/gen_config/target/release/gen_config $bin
    
    cp -v $hw_sim/target/release/simulator $bin

    cp -v $qline_backend/target/release/node $bin
    cp -v $qline_backend/target/release/km-server $bin

}

# Check that exactly one argument is provided
[ $# -eq 1 ] || usage

case "$1" in
    pull)
        pull
        ;;
    build)
        build 
        ;;
    install)
        install
        ;;
    all)
        pull; build; install;
        ;;
    *)
        echo "Error: Unknown command '$1'"
        usage
        ;;
esac
