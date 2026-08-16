# Makefile for Cosmology Monograph
# Flyxion — August 2026

MAIN = monograph
LATEX = pdflatex
BIBTEX = bibtex
LATEXFLAGS = -interaction=nonstopmode -file-line-error

.PHONY: all clean cleanall view

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

clean:
	rm -f $(MAIN).aux $(MAIN).log $(MAIN).out $(MAIN).toc $(MAIN).lof $(MAIN).lot
	rm -f $(MAIN).bbl $(MAIN).blg
	rm -f *.aux

cleanall: clean
	rm -f $(MAIN).pdf

# Individual chapter compilation (add as needed)
