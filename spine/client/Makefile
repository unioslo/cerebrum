##
## Makefile for SpineClient
##

INSTALL = /usr/bin/install -c
pythondir = /home/local/kandal/install/lib/python2.3/site-packages

.PHONY: all install install-lib clean distclean

sources = $(wildcard *.py)

all: 

install: install-lib

install-lib: $(sources)
	$(INSTALL) -v -m 644 $(sources) $(pythondir)
	$(INSTALL) -v -m 644 ../lib/server/idl/SpineCore.idl $(pythondir)

clean:

distclean: clean

