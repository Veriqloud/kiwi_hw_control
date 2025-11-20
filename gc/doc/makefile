targets = scheme.svg

all: $(targets)

%.svg: %.dvi
	dvisvgm --font-format=WOFF2 --exact --zoom=1.2 --bbox=papersize $<
	rm $<

%.dvi: %.tex
	latex $< 
	rm $(basename $@).log $(basename $@).aux

clean:
	rm -f $(targets)
	rm -f *.dvi


