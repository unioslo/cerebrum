# -*- coding: iso-8859-1 -*-

# Copyright 2003 University of Oslo, Norway
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

class StudentInfoParser(xml.sax.ContentHandler):
    """Parses the StudentInfo file, (which is the result of running
    merge_xml_files on the output from
    import_from_FS.write_person_info).  The file contains everything
    we want to know about students.  This makes it easier to perform
    decisions on what to do with a student, as all relevant
    information is available at the same time.

    This class obsoletes TopicsParser and StudieprogsParser which
    probably should be removed."""

    def __init__(self, info_file, call_back_function, logger):
        self._logger = logger
        self.personer = []
        self.elementstack = []
        self.call_back_function = call_back_function
        xml.sax.parse(info_file, self)

    def startElement(self, name, attrs):
        tmp = {}
        for k in attrs.keys():
            tmp[k.encode('iso8859-1')] = attrs[k].encode('iso8859-1')
        name = name.encode('iso8859-1')
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
            if name in ("fagperson", "opptak", "alumni", "privatist_studieprogram", "aktiv", "privatist_emne", "regkort", "eksamen", "evu", "permisjon", "tilbud"):
                self.person.setdefault(name, []).append(tmp)
            else:
                self._logger.warn("unknown person element: %s" % name)
        self.elementstack.append(name)
            
    def endElement(self, name):
        if name == "person":
            self.call_back_function(self.person)
        self.elementstack.pop()

class GeneralDataParser(xml.sax.ContentHandler, object):
    """Parses the xml file that contains definitions"""

    def startElement(self, name, attrs):
        self.t_data = {}
        for k in attrs.keys():
            self.t_data[k.encode('iso8859-1')] = attrs[k.encode('iso8859-1')].encode('iso8859-1')

    def endElement(self, name):
        if name == self.entry_tag:
            self.data.append(self.t_data)

    def __init__(self, data_file, entry_tag):
        self.data = []
        self.entry_tag = entry_tag
        xml.sax.parse(data_file, self)

    def __iter__(self):
        return self

    def next(self):
        """Returns a dict with data about all studieprogs for the next person."""
        try:
            return self.data.pop(0)
        except IndexError:
            raise StopIteration, "End of file"

class StudieprogDefParser(GeneralDataParser):
    def __init__(self, studieprogs_file):
        super(StudieprogDefParser, self).__init__(studieprogs_file, 'studprog')

class EmneDefParser(GeneralDataParser):
    def __init__(self, studieprogs_file):
        super(EmneDefParser, self).__init__(studieprogs_file, 'emne')

# arch-tag: 0d9f1ca2-1647-47f4-a395-cac03e07a4d3
