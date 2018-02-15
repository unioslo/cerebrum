# -*- coding: utf-8 -*-
# Copyright 2015 University of Oslo, Norway
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
"""Reads information from FS dumps about which study program(s) a student is associated with
and maps it to the person ID."""

from __future__ import unicode_literals

import cereconf

from os.path import join
from collections import defaultdict

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.xmlutils.GeneralXMLParser import GeneralXMLParser
from Cerebrum.FileCache import PickleCache


def fetch_study_programs(db, logger):
    co = Factory.get('Constants')(db)
    pe = Factory.get('Person')(db)

    def handle_aktiv(data, stack):
        aktiv = stack[-1][-1]
        pe.clear()
        try:
            pe.find_by_external_id(
                id_type=co.externalid_studentnr,
                external_id=aktiv['studentnr_tildelt'],
                source_system=co.system_fs)
        except Errors.NotFoundError:
            return
        study_programs[pe.entity_id].append({
            'studieprogramkode': aktiv['studieprogramkode'],
            'arstall_kull': aktiv['arstall_kull'],
        })

    study_programs = defaultdict(list)
    parser_config = [(['data', 'person', 'aktiv'], handle_aktiv)]
    GeneralXMLParser(parser_config, join(cereconf.FS_DATA_DIR, 'merged_persons.xml'))
    return study_programs


class StudentStudyProgramCache(PickleCache):
    def __init__(self, **kwargs):
        self.name = 'fs-student-study-programs'
        self.build_callback = fetch_study_programs
        super(StudentStudyProgramCache, self).__init__(**kwargs)
