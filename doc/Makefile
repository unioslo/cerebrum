# documentation build options

CEREDOC = $(PWD) 
CERESRC = $(PWD)/..
SP_ENCODING = XML
SP_CHARSET_FIXED = YES

# generic settings

DESTDIR     =
prefix      = /usr

docdir      = $(prefix)/share/doc/cerebrum-doc
htmldir     = $(docdir)/html
mandir      = $(prefix)/share/man
man1dir     = $(mandir)/man1

# there are no manpages yet, but they will be called
MAN         = makedb.1 jbofh.1 bofhd.1

INSTALL_DATA = install --mode=644



all:

install: 
	install -d 	$(DESTDIR)$(docdir)  \
			$(DESTDIR)$(htmldir) \
			$(DESTDIR)$(man1dir)
	$(INSTALL_DATA)	 
	touch stamp-install
clean:
	rm -f blub
	rm -f stamp-build stamp-html stamp-pdf

build: 
	$(PWD)/doc/scripts/build.py --build-contents contents.rst
	$(PWD)/doc/scripts/build.py --xml book.xml
	(cd build; db2pdf book.xml)

# arch-tag: b7c792a8-bc44-4fcf-a88c-3dd56ed3ca73
