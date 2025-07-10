PROGS := ../gc ../qber ../config/gen_config

# Default target: build all
all: $(PROGS)

# Generic build rule: each dir has Cargo.toml
$(PROGS):
	cd $@ && cargo build --release

# Clean all
clean:
	@for d in $(PROGS); do \
		(cd $$d && cargo clean); \
	done

.PHONY: all $(PROGS) run clean




