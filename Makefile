# IEUMUN 2026 study guides.
#
#   make            convert every changed source and rebuild its PDF into out/
#   make -j8        the same, several guides at a time
#   make wto        one guide (any slug from SG_config/)
#   make check      print the build checks for every guide
#   make preview    render every guide's pages as PNGs into .preview/
#   make clean      remove everything generated (guides/, build/, out/)
#
# A guide is rebuilt when its Word source, cover, or SG_config/<slug>.json
# changes; a change to scripts/ reconverts all guides and a change to template/
# rebuilds all PDFs. On macOS without an accepted Xcode licence, run ./make.

PYTHON ?= python3
DRIVER := scripts/guides.py
SLUGS := $(patsubst SG_config/%.json,%,$(wildcard SG_config/*.json))
SCRIPTS := scripts/docx2guide.py scripts/guides.py
TEMPLATE := $(wildcard template/*)

.PHONY: all check preview clean list $(SLUGS)
# Nothing built here is a throw-away intermediate.
.SECONDARY:

all: $(SLUGS:%=build/stamps/%.published)
	@$(PYTHON) $(DRIVER) prune

$(SLUGS): %: build/stamps/%.published

-include build/deps.mk

build/deps.mk: $(wildcard SG_config/*.json) $(DRIVER)
	@$(PYTHON) $(DRIVER) deps

guides/%/main.tex: SG_config/%.json $(SCRIPTS) template/latexmkrc
	@$(PYTHON) $(DRIVER) convert $*

guides/%/main.pdf: guides/%/main.tex $(TEMPLATE)
	@echo "[$*] building PDF"
	@$(PYTHON) $(DRIVER) pdf $*

build/stamps/%.published: guides/%/main.pdf
	@$(PYTHON) $(DRIVER) publish $*

check:
	@$(PYTHON) $(DRIVER) check

preview:
	@for s in $(SLUGS); do $(PYTHON) $(DRIVER) preview $$s; done

list:
	@$(PYTHON) $(DRIVER) list

clean:
	rm -rf build out guides/*
