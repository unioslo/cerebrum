INSTALL = cp

prefix=/usr/local
pythonprefix=$(prefix)/lib/site-python

all:

install:

dist:

distcheck: dist

init:
	make -C testsuite check 2>&1 | tee testsuite/log-init.out


check:
	( \
	    PYTHONPATH=`pwd` python2.2 testsuite/Run.py  -v ; \
	) 2>&1 | tee testsuite/log-check.out

fullcheck: init check

clean:

distclean:
