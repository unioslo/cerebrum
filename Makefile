INSTALL = cp

prefix=/usr/local
pythonprefix=$(prefix)/lib/site-python

all:

install:

dist:

distcheck: dist

check:
	make -C testsuite check 2>&1 | tee testsuite/check.log

clean:

distclean:
