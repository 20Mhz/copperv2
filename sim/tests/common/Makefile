
SCRIPTS_DIR ?= ../../../scripts
COMMON_DIR ?= ../common

LINKER_SCRIPT = $(COMMON_DIR)/linker.ld
CC = riscv64-unknown-elf-gcc
OBJCOPY = riscv64-unknown-elf-objcopy
CFLAGS += -march=rv32i -mabi=ilp32 -I$(COMMON_DIR)
LDFLAGS += -march=rv32i -mabi=ilp32

crt0.o: $(COMMON_DIR)/crt0.S
	$(CC) $(CFLAGS) -c $< -o $@

syscalls.o: $(COMMON_DIR)/syscalls.c
	$(CC) $(CFLAGS) -c $< -o $@

syscalls.E: $(COMMON_DIR)/syscalls.c
	$(CC) $(CFLAGS) -E $< -o $@

%.E: %.c
	$(CC) $(CFLAGS) -E $< -o $@

%.hex: %.o crt0.o syscalls.o
	$(CC) $(LDFLAGS) -Wl,-T,$(LINKER_SCRIPT),-Bstatic -nostartfiles -ffreestanding $^ -o $(@:.hex=.elf)
	$(SCRIPTS_DIR)/utils.py debug $(@:.hex=.elf) || true
	$(OBJCOPY) -O verilog $(@:.hex=.elf) $@

.PHONY: clean
clean:
	rm -fv *.o *.elf *.debug *.E *.hex
