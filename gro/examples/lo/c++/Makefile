# This file is part of Cerebrum
# MakeFile for the LO example C++ client
#

CC=g++
CXXFLAGS=-g -Wall -O2 -I`pwd` -I/usr/include/omniORB4 -I/usr/kerberos/include
LDFLAGS=-lomniORB4 -lssl -lcrypto -lomnisslTP -lomniDynamic4

all: lo_test

CORBA_SOURCES = groSK.cc classesSK.cc errorsSK.cc
$(CORBA_SOURCES) gro.hh: ../../../idl/*.idl
		omniidl -bcxx ../../../idl/classes.idl
		omniidl -bcxx ../../../idl/errors.idl
		omniidl -bcxx ../../../idl/gro.idl


lo_test: lo_test.o $(CORBA_SOURCES:.cc=.o)
lo_test.o: lo_test.cc gro.hh

clean: 
	rm -f lo_test
	rm -f *.o
distclean: clean
	rm -f $(CORBA_SOURCES)
	rm -f $(CORBA_SOURCES:.cc=.hh)
	rm -f $(CORBA_SOURCES:SK.cc=.hh)

# arch-tag: 71a6c3f9-418e-40de-9661-7fa4e5a8b30d
