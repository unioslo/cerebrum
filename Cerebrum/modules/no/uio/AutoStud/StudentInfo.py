# -*- coding: utf-8 -*-

# Copyright 2003-2023 University of Oslo, Norway
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
Parsers for person/student data from FS.

These parsers are mainly for use with the ``merged_persons.xml`` file, which
can be generated by running ``merge_xml_files.py`` on the output from
``import_from_FS.write_person_info``.  The file contains everything we want to
know about students (or other persons from FS).
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import xml.sax


class StudentInfoParser(xml.sax.ContentHandler):
    """
    Parses the StudentInfo file.

    The file structure is:

    <data>
      <person fodselsdato="..." personnr="..." ...>
        <.../>
      </person>
    </data>
    """

    def __init__(self, info_file, call_back_function, logger):
        self._logger = logger
        self.personer = []
        self.elementstack = []
        self.call_back_function = call_back_function
        xml.sax.parse(info_file, self)

    def startElement(self, name, attrs):  # noqa: N802
        tmp = dict(attrs)
        if len(self.elementstack) == 0:
            if name == "data":
                pass
            else:
                self._logger.warn("unknown element: %s" % name)
        elif len(self.elementstack) == 1:
            if name == "person":
                self.person = {'fodselsdato': tmp['fodselsdato'],
                               'personnr': tmp['personnr']}
            else:
                self._logger.warn("unknown element: %s" % name)
        elif self.elementstack[-1] == "person":
            if name in ("fagperson", "opptak", "alumni",
                        "privatist_studieprogram", "aktiv", "emnestud",
                        "privatist_emne", "regkort", "eksamen", "evu",
                        "permisjon", "tilbud", "drgrad", "nettpubl"):
                self.person.setdefault(name, []).append(tmp)
            else:
                self._logger.warn("unknown person element: %s" % name)
        self.elementstack.append(name)

    def endElement(self, name):  # noqa: N802
        if name == "person":
            self.call_back_function(self.person)
        self.elementstack.pop()


class GeneralDataParser(xml.sax.ContentHandler, object):
    """
    Extract data from a given *entry_tag* in any XML file.

    This parser simply finds all occurrences of a given element name in an XML
    file.  The result is an iterator that returns a dict of the attributes of
    each occurrence.
    """

    def __init__(self, data_file, entry_tag):
        self.data = []
        self.entry_tag = entry_tag
        xml.sax.parse(data_file, self)

    def startElement(self, name, attrs):  # noqa: N802
        self.t_data = dict(attrs)

    def endElement(self, name):  # noqa: N802
        if name == self.entry_tag:
            self.data.append(self.t_data)

    def __iter__(self):
        return self

    def __next__(self):
        try:
            return self.data.pop(0)
        except IndexError:
            raise StopIteration

    def next(self):
        # PY2 compat
        return self.__next__()


class StudieprogDefParser(GeneralDataParser):
    """Parse and find <studprog> element attributes. """

    def __init__(self, studieprogs_file):
        super(StudieprogDefParser, self).__init__(studieprogs_file, 'studprog')


class EmneDefParser(GeneralDataParser):
    """Parse and find <emne> element attributes. """

    def __init__(self, studieprogs_file):
        super(EmneDefParser, self).__init__(studieprogs_file, 'emne')
