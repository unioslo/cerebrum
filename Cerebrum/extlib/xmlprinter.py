"""
help write out XML documents

>>> import xmlprinter
>>> import StringIO
>>> fp = StringIO.StringIO()
>>> xp = xmlprinter.xmlprinter(fp) # The fp need only have a write() method
>>> xp.startDocument()
>>> xp.notationDecl("html", "-//W3C//DTD XHTML 1.1//EN", "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd")
>>> xp.startElement('html',
...                 {'xmlns': "http://www.w3.org/1999/xhtml",
...                  'xml:lang': "en-us"})
>>> xp.data("\\n")
>>> xp.startElement('head')
>>> xp.startElement('title')
>>> xp.data("This is the title")
>>> xp.endElement()        # we may omit the element name ('title')
>>> xp.endElement('head')  # or we can include it
>>> xp.data("\\n")
>>> xp.startElement('body')
>>> xp.data("\\n")
>>> xp.startElement('p')
>>> xp.data("This is some information in a paragraph.")
>>> xp.endElement('p')
>>> xp.data("\\n")
>>> xp.emptyElement('hr', {'style': 'color: red'})
>>> xp.data("\\n")
>>> xp.endDocument()       # by default closes remaining tags
>>> print fp.getvalue(),
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en-us">
<head><title>This is the title</title></head>
<body>
<p>This is some information in a paragraph.</p>
<hr style="color: red" />
</body></html>

This module does nothing fancy like indenting.

Distributions for this module can be downloaded at
https://sourceforge.net/project/showfiles.php?group_id=60881


Copyright (C) 2002 Frank J. Tobin, ftobin@neverending.org

This library is free software; you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as
published by the Free Software Foundation; either version 2.1 of the
License, or (at your option) any later version.

The idea for this module was taken from Perl's XML::Writer.
"""

__version__  = "0.1.0"
__revision__ = "$Id$"


class WellFormedError(Exception):
    pass

    
class xmlprinter(object):
    """We try to ensure a well-formed document, but won't check
    things like the validity of element names.
    Method raise WellFormedError if there are well-formed-ness problems.
    """

    xml_version = '1.0'
    
    __slots__ = ['fp', '_elstack', '_inroot',
                 '_past_doctype', '_past_decl', '_finished',
                 '_indent_level', '_data_mode', '_has_data',
                 '_encoding', '_input_encoding']

    def __init__(self, fp, indent_level=0, data_mode=0, input_encoding='UTF-8'):
        """fp is a file-like object, needing only a write() method"""
        self._finished     = False
        self._past_doctype = False
        self._past_decl    = False
        self._elstack      = []
        self._inroot       = True
        self.fp           = fp
        self._indent_level = indent_level
        self._data_mode = data_mode
        self._input_encoding = input_encoding

    def startDocument(self, encoding='UTF-8'):
        """Begin writing out a document, including the XML declaration.
        Currently the encoding header can be changed from the default,
        but it won't affect how the rest of the document is encoded.
        """

        self._encoding = encoding
        if self._past_decl:
            raise WellFormedError, "past allowed point for XML declaration"
        
        self.fp.write('<?xml version=%s encoding=%s?>\n'
                      % (quoteattr(self.xml_version),
                         quoteattr(encoding)))
        self._past_decl = True


    def notationDecl(self, name, public_id=None, system_id=None):
        """Insert DOCTYPE declaration.
        Can only be added right after document start.
        Optional for a well-formed document.
        At least a public_id or system_id must be specified if called."""
        if self._past_doctype:
            raise WellFormedError, "past allowed point for doctype"
        
        self.fp.write('<!DOCTYPE %s' % name)

        if public_id is not None and system_id is None:
            raise TypeError, "must have system_id with public_id"

        if public_id is not None:
            self.fp.write(" PUBLIC %s %s" % (quoteattr(public_id),
                                             quoteattr(system_id)))
        elif system_id is not None:
            self.fp.write(" SYSTEM %s" % quoteattr(system_id))

        self.fp.write(">\n")
        self._past_doctype = True


    def startElement(self, name, attrs={}):
        """Start element 'name' with attributes 'attrs'. (<example>)"""
        self._past_doctype = True
        self._past_decl    = True
        
        if self._finished:
            raise WellFormedError, "attempt to add second root element"

        if self._data_mode:
            self.fp.write("\n")
        self.fp.write(" " * (self._indent_level * len(self._elstack)) +
                      "<%s" % name)
        
        for attr, val in attrs.items():
            self.fp.write(" %s=%s" % (attr, quoteattr(val)))

        self.fp.write(">")
        self._elstack.append(name)
        self._inroot = True
        self._has_data = 0

    def comment(self, data):
        self.fp.write("<!-- %s -->" % data);
        if len(self._elstack) == 0:
            self.fp.write("\n")

    def data(self, data):
        """Add text 'data'."""
        if not self._inroot:
            raise WellFormedError, "attempt to add data outside of root"
        self._has_data = 1
        data = escape(data)
        if self._input_encoding != self._encoding:
            if self._input_encoding == 'UTF-8':
                data = data.encode(self._encoding)
            else:
                data = data.decode(self._input_encoding).encode(self._encoding)
        self.fp.write(data)

    def dataElement(self, name, data, attrs={}):
        self.startElement(name, attrs)
        self.data(data)
        self.endElement(name)        

    def emptyElement(self, name, attrs={}):
        """Add an empty element (<example />)"""
        if not self._inroot:
            raise WellFormedError, "attempt to add element outside of root"

        if self._data_mode:
            self.fp.write("\n")
        self.fp.write(" " * (self._indent_level * len(self._elstack)) +
                      "<%s" % name)
        for attr, val in attrs.items():
            self.fp.write(" %s=%s" % (attr, quoteattr(val)))
        self.fp.write(" />")
        

    def endElement(self, name=None):
        """End the element 'name'.
        If 'name' is None, then end the most recently-opened element.
        (</example>).

        If the last element is being closed, then it 
        """
        popel = self._elstack.pop()

        if name is not None and name != popel:
            raise WellFormedError, "ending an unstarted element %s" \
                  % repr(name)

        if name is None:
            name = popel
        if not self._has_data:
            if self._data_mode:
                self.fp.write("\n")
            self.fp.write(" " * (self._indent_level * len(self._elstack)))
        self.fp.write("</%s>" % name)

        if len(self._elstack) == 0:
            self._inroot = False
            # ensures a newline at the end of a text file
            self.fp.write("\n")
        self._has_data = 0

    def endDocument(self, autoclose=True):
        """Finish up a document.
        If autoclose is True, then also close any unclosed elements.
        Else, all elements must already be closed.
        """
        if self._finished:
            raise WellFormedError, "attempt to re-end a _finished document"

        if autoclose:
            while len(self._elstack) > 0:
                self.endElement()

        if len(self._elstack) > 0:
            raise WellFormedError, "attempt to re-end a _finished document"
        
        self._finished = True


def escape(data):
    """Escape &, <, and > in a string of data; used for character data."""
        
    return data.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    

def quoteattr(data):
    """Escape and quote an attribute value."""
    data = escape(data)

    # We don't just turn " into &quot;, we'll use single quotes
    # if possible to retain the 'look' better.
    if '"' in data:
        if "'" in data:
            data = '"%s"' % data.replace('"', "&quot;")
        else:
            data = "'%s'" % data
    else:
        data = '"%s"' % data

    return data



def _test():
    import doctest, xmlprinter
    return doctest.testmod(xmlprinter)


if __name__ == '__main__':
    _test()

# arch-tag: 659e3292-71cb-4b37-82c9-1d278ca9c3b8
