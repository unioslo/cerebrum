INSTALL = cp

prefix=/usr/local
pythonprefix=$(prefix)/lib/site-python

all:

install:
	./setup.py install install_data --install-dir=$(prefix)

dist:

distcheck: dist

bootstrap:
	make -C testsuite bootstrap 2>&1 | tee testsuite/log-bootstrap.out

testrun:
	make -C testsuite testrun 2>&1 | tee testsuite/log-testrun.out


check:
	( \
	    PYTHONPATH=`pwd` python2.2 testsuite/Run.py  -v ; \
	) 2>&1 | tee testsuite/log-check.out

fullcheck: bootstrap check testrun

clean:

distclean:
