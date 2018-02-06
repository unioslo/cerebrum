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

from __future__ import unicode_literals
import re
from Cerebrum.extlib import xmlprinter


class ABCXMLWriter(object):
    """Class for writing objects to XML again. May become useful
    when ABC Enterprise is to be used as an export format. For now
    it's only used as selftest on the import bit. Not complete.
    This is just a skeleton of what the ABCEnterprise class calls."""

    def __init__(self, settings):
        self.sett = settings
        filename = re.sub(".xml$", "-parsed.xml", self.sett.variables['filename'])
        self.fd = open(filename, "w")

        self.xp = xmlprinter.xmlprinter(self.fd, indent_level=2)
        self.xp.startDocument()
        self.xp.startElement('document')
        self.xp.newline()

    def _add_elem(self, tag, data=None, attr={}):
        self.xp.startElement(tag, attr)
        if data: self.xp.data(data)
        self.xp.endElement(tag)
        self.xp.newline()

    def parse_settings(self):
        self.xp.startElement("properties")
        self.xp.newline()
        for i,j in (("datasource", self.sett.variables['datasource']),
                    ("target", self.sett.variables['target']),
                    ("timestamp", self.sett.variables['timestamp'])):
            self._add_elem(i, j)
        self.xp.startElement("types")
        self.xp.newline()
#         for type in self.settings.types.keys():
#             for value in self.settings.types[type]:
#                 txt = ""
#                 attr = dict()
#                 if isinstance(value, tuple):
#                     ln = len(value)
#                     if ln > 0:
#                         txt = value[0]
#                     if ln > 1:
#                         attr["subject"] = value[1]
#                     if ln > 2:
#                         attr["object"] = value[2]
#                 else:
#                     txt = value
#                 self._add_elem(type, txt, attr)
        self.xp.endElement("types")
        self.xp.newline()
        self.xp.endElement("properties")
        self.xp.newline()


    def parse_persons(self, iterator):
        """Iterate persons. Add them to the tree."""
        for person in iterator:
            print person


    def parse_orgs(self, iterator):
        """Iterate over organizations. Add the org to the tree."""
        for org in iterator:
            print org
            if org.ou:
                for o in org.ou:
                    print o


    def parse_groups(self, iterator):
        for group in iterator:
            print group


    def parse_relations(self, iterator):
        for rel in iterator:
            print rel


    def end_parse(self):
        self.xp.endDocument()
        self.fd.close()

