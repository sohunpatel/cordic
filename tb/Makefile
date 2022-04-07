TOPLEVEL_LANG ?= verilog
SIM ?= icarus

PWD=$(shell pwd)

ifeq ($(TOPLEVEL_LANG),verilog)
    VERILOG_SOURCES = $(PWD)/../hdl/cordic.v

    ifneq ($(filter $(SIM),riviera activehdl),)
        COMPILE_ARGS += -sv2k12
    endif

else ifeq ($(TOPLEVEL_LANG),vhdl)
    VHDL_SOURCES = $(PWD)/../hdl/matrix_multiplier_pkg.vhd $(PWD)/../hdl/matrix_multiplier.vhd

    ifneq ($(filter $(SIM),ghdl questa modelsim riviera activehdl),)
        # ghdl, questa, and aldec all use SIM_ARGS with '-g' for setting generics
        SIM_ARGS += -gDATA_WIDTH=$(DATA_WIDTH) -gA_ROWS=$(A_ROWS) -gB_COLUMNS=$(B_COLUMNS) -gA_COLUMNS_B_ROWS=$(A_COLUMNS_B_ROWS)
    else ifneq ($(filter $(SIM),ius xcelium),)
        SIM_ARGS += -generic "matrix_multiplier:DATA_WIDTH=>$(DATA_WIDTH)" -generic "matrix_multiplier:A_ROWS=>$(A_ROWS)" -generic "matrix_multiplier:B_COLUMNS=>$(B_COLUMNS)" -generic "matrix_multiplier:A_COLUMNS_B_ROWS=>$(A_COLUMNS_B_ROWS)"
    endif

    ifeq ($(SIM),ghdl)
        EXTRA_ARGS += --std=08
        SIM_ARGS += --wave=wave.ghw
    else ifneq ($(filter $(SIM),questa modelsim riviera activehdl),)
        COMPILE_ARGS += -2008
    endif
else
    $(error "A valid value (verilog or vhdl) was not provided for TOPLEVEL_LANG=$(TOPLEVEL_LANG)")
endif

# Fix the seed to ensure deterministic tests
export RANDOM_SEED := 123456789

TOPLEVEL    := cordic
MODULE      := tb

include $(shell cocotb-config --makefiles)/Makefile.sim


# Profiling

DOT_BINARY ?= dot

test_profile.pstat: sim

callgraph.svg: test_profile.pstat
	$(shell cocotb-config --python-bin) -m gprof2dot -f pstats ./$< | $(DOT_BINARY) -Tsvg -o $@

.PHONY: profile
profile:
	COCOTB_ENABLE_PROFILING=1 $(MAKE) callgraph.svg