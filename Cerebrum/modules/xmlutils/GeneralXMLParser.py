# -*- coding: utf-8 -*-
# Copyright 2005 University of Oslo, Norway
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

import xml.sax

class GeneralXMLParser(xml.sax.ContentHandler):
    """This is a general SAX-based XML parser capable of generating
    callbacks once requested information has been parsed.  The cfg
    constructor parameter has the format::

      cfg = ((['tag1, 'tag1_1'], got_tag1_1_callback))

    Once parsing of tag1_1 has been completed, the callback function
    is called with the arguments dta, elem_stack.  elem_stack contains
    a list of (entity_name, attrs_dict) tuples up to the root XML
    node.  dta contains a list of (entity_name, attrs_dict, children)
    tuples inside the requested tag.  children has the same format as
    dta, thus if one use something like cfg = ((['root_tag'], cb)),
    the dta in the callback would contain a parsed tree of the entire
    XML file.

    The parser is only suitable for XML files that does not contain
    text parts outside the tags.
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
            parser.setFeature(xml.sax.handler.feature_external_ges, 0)
        except xml.sax._exceptions.SAXNotRecognizedException:
            # Older API versions don't try to handle external entities
            pass
        parser.parse(xml_file)

    def characters(self, ch):
        self.var = None
        tmp = ch.encode('iso8859-1').strip()
        if tmp:
            self.var = tmp

    def startElement(self, ename, attrs):
        self.ename = ename
        tmp = {}
        for k in attrs.keys():
            tmp[k.encode('iso8859-1')] = attrs[k].encode('iso8859-1')
        ename = ename.encode('iso8859-1')
        self._elementstack.append(ename)
        if not self._in_dta:
            self.top_elementstack.append((ename, tmp))
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
            self._tmp_pos.append([ename, self.var, tmp, children])
            self.var = None
            self._tmp_pos = children

    def endElement(self, ename):
        if ename != self.ename and self.var != None:
            raise ValueError, "Cannot have both text and children."
        elif ename == self.ename and self.var != None:
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

    def dump_tree(dta, lvl=0):
        for ename, attrs, children in dta:
            print "%s%s %s" % (" " * lvl * 2, ename, attrs)
            GeneralXMLParser.dump_tree(children, lvl+1)
    dump_tree = staticmethod(dump_tree)

