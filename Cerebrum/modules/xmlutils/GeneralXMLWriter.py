#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2007 University of Oslo, Norway
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

# $Id$

from Cerebrum.extlib import xmlprinter

""" 
Module documentation goes here.

"""

__version__ = "$Revision$"
# $Source$

class XMLWriter(object):
    # TODO: should produce indented XML for easier readability
    def __init__(self, output_stream):
        self.gen = xmlprinter.xmlprinter(
            output_stream, indent_level=2, data_mode=1,
            input_encoding='ISO-8859-1')

    def startTag(self, tag, attrs={}):
        a = {}
        for k in attrs.keys():   # saxutils don't like integers as values
            a[k] = str(attrs[k])
        self.gen.startElement(tag, a)

    def endTag(self, tag):
        self.gen.endElement(tag)

    def emptyTag(self, tag, attrs={}):
        a = {}
        for k in attrs.keys():   # saxutils don't like integers as values
            a[k] = str(attrs[k])
        self.gen.emptyElement(tag, a)

    def dataElement(self, tag, data, attrs={}):
        a = {}
        for k in attrs.keys():
            a[k] = str(attrs[k])
        self.gen.dataElement(tag, data, a)

    def comment(self, data):
        self.gen.comment(data)

    def notationDecl(self, name, public_id=None, system_id=None):
        self.gen.notationDecl(name, public_id, system_id)
    
    def startDocument(self, encoding):
        self.gen.startDocument(encoding)

    def endDocument(self):
        self.gen.endDocument()

