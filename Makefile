# Makefile for Cosmology Monograph
# Flyxion — August 2026

MAIN = monograph
LATEX = pdflatex
BIBTEX = bibtex
LATEXFLAGS = -interaction=nonstopmode -file-line-error

.PHONY: all clean cleanall view reknotting-test

all: $(MAIN).pdf

$(MAIN).pdf: $(MAIN).tex references.bib
	$(LATEX) $(LATEXFLAGS) $(MAIN)
	$(BIBTEX) $(MAIN)
	$(LATEX) $(LATEXFLAGS) $(MAIN)
	$(LATEX) $(LATEXFLAGS) $(MAIN)

quick: $(MAIN).tex
	$(LATEX) $(LATEXFLAGS) $(MAIN)

view: $(MAIN).pdf
	xdg-open $(MAIN).pdf &

reknotting-test:
	cd experiments/python && python3 -m unittest -v test_reknotting_model.py
	cd experiments/python && python3 reknotting_model.py --output reknotting-output

clean:
	rm -f $(MAIN).aux $(MAIN).log $(MAIN).out $(MAIN).toc $(MAIN).lof $(MAIN).lot
	rm -f $(MAIN).bbl $(MAIN).blg
	rm -f *.aux

cleanall: clean
	rm -f $(MAIN).pdf

# Individual chapter compilation (add as needed)
