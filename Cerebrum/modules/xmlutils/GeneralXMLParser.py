# -*- coding: utf-8 -*-
#
# Copyright 2005-2026 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
"""
A generic callback-based XML parser.

This is a legacy module, and the parser is fairly buggy.  Only use for simple
documents.  For new use-cases, please use the built-in XPath support in
xml.etree.ElementTree:
::

    # rather than:

    def foo_handler(data, stack):
        ...

    GeneralXMLParser(((["data, "foo"], foo_handler),), "myfile.xml")

    # use:

    from xml.etree import ElementTree
    tree = ElementTree.parse("myfile.xml")
    root = tree.getroot()

    for elem in root.findall("./data/foo"):
        ...

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import xml.sax


class GeneralXMLParser(xml.sax.ContentHandler, object):
    """
    This is a general SAX-based XML parser for running callbacks.

    The parser runs callbacks for a given XPath-like list of element names. 
    The callback gets two arguments:

    ``<data>``
        A tuple with information on the matched element.

        The tuple contains the element name, attributes, and a list
        of child elements, e.g.: ``("foo", {"x": 10, "y": 20}, [])``).

        Each child element is a similar tuple, but additionally contains any
        text content in the child element.  Inclusion of text/element value is
        very buggy.  Unsure why the child elements get this extra field...

    ``<stack>``
        A list of parent elements.  Each element is a tuple with the element
        name and attributes: e.g.: ``[("foo", {'x': 10}), ("data", {})]``

    Given the configuration:
    ::

        ((['data, 'foo'], foo_handler) (['data, 'bar'], bar_handler))

    ... the parser will call the given handler callback for each element where
    the stack matches the given list.  I.e. ``foo_handler`` will be called for
    all elements matching XPath ``/data/foo``.
    """

    def __init__(self, cfg, xml_file):
        self._elementstack = []
        self.top_elementstack = []
        self.cfg = cfg
        self._in_dta = None
        parser = xml.sax.make_parser()
        parser.setContentHandler(self)
        # Don't resolve external entities
        try:
            parser.setFeature(xml.sax.handler.feature_external_ges, False)
        except xml.sax._exceptions.SAXNotRecognizedException:
            # Older API versions don't try to handle external entities
            pass
        parser.parse(xml_file)

    def characters(self, ch):
        self.var = ch.strip() or None

    def startElement(self, ename, attrs):  # noqa: N802
        attrs_dict = dict(attrs)
        self.ename = ename
        self._elementstack.append(ename)
        if not self._in_dta:
            self.top_elementstack.append((ename, attrs_dict))
            for loc, cb in self.cfg:
                if loc == self._elementstack:
                    self._in_dta = loc
                    self._cb = cb
                    self._start_pos = []
                    self._tmp_pos = self._start_pos
                    self._child_stack = [self._start_pos]
                    break
        else:
            children = []
            self._child_stack.append(children)
            self._tmp_pos.append([ename, self.var, attrs_dict, children])
            self.var = None
            self._tmp_pos = children

    def endElement(self, ename):  # noqa: N802
        if ename != self.ename and self.var is not None:
            raise ValueError("Cannot have both text and children.")
        elif ename == self.ename and self.var is not None:
            self._child_stack[0][-1][1] = self.var
            self.var = None
        if self._in_dta == self._elementstack:
            self._cb(self._start_pos, self.top_elementstack)
            self._in_dta = None
            self.top_elementstack.pop()
        elif not self._in_dta:
            self.top_elementstack.pop()
        else:
            self._child_stack.pop()
            if self._child_stack:
                self._tmp_pos = self._child_stack[-1]
        self._elementstack.pop()

    @staticmethod
    def dump_tree(dta, level=0):
        for item in dta:
            if len(item) == 3:
                ename, attrs, children = item
            else:
                ename, _, attrs, children = item
            print("{}{} {}".format(" " * level * 2, ename, attrs))
            GeneralXMLParser.dump_tree(children, level + 1)
