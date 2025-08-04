PROGS := ../gc ../qber ../config/gen_config

# Default target: build all
all: $(PROGS)

# Generic build rule: each dir has Cargo.toml
$(PROGS):
	cd $@ && cargo build --release

# copy everthing into ~/bin/
install:
	cp ../gc/target/release/alice ~/bin/gc_alice
	cp ../gc/target/release/bob ~/bin/gc_bob
	cp ../qber/target/release/alice ~/bin/qber_alice
	cp ../qber/target/release/bob ~/bin/qber_bob
	cp ../config/gen_config/target/release/gen_config ~/bin/

# Clean all
clean:
	@for d in $(PROGS); do \
		(cd $$d && cargo clean); \
	done

.PHONY: all $(PROGS) run clean




