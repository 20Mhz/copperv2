## Useful for chisel debugging: CHISELFLAGS="--no-constant-propagation --no-dce"

PYTHON ?= $(if $(shell which python),python,python3)
SHELL = bash
WBXBAR_SOURCE := src/main/resources/external/wb2axip/rtl/wbxbar.v

.PHONY: all
all: work/sim/result.xml

.PHONY: clean
clean:
	rm -rf work/rtl work/sim out/

.venv: requirements.txt
	rm -rf .venv
	$(PYTHON) -m venv .venv
	source .venv/bin/activate; pip install wheel
	source .venv/bin/activate; pip install -r requirements.txt

$(WBXBAR_SOURCE):
	git submodule update --init

work/rtl/copperv2.v: $(WBXBAR_SOURCE) $(shell find ./src -name '*.scala' -o -name '*.v')
	./scripts/mill copperv2.run $(CHISELFLAGS)

work/sim/result.xml: work/rtl/copperv2.v .venv $(shell find ./sim -name '*.py')
	source .venv/bin/activate; pytest -n $(shell nproc) --junitxml="$@"
