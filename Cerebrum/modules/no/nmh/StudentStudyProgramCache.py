# -*- coding: utf-8 -*-
# Copyright 2015-2025 University of Oslo, Norway
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
Translate study program participation to a participation cache.

Reads information from FS dumps about which study program(s) a student is
associated with and builds a mapping cache with:
::

    {
        <person-id>: {
            'studieprogramkode': <study-program-id>,
            'arstall_kull': <study-program-year>,
        },
        ...
    }
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging
import os

import cereconf
from Cerebrum import Errors
from Cerebrum import FileCache
from Cerebrum.Utils import Factory
from Cerebrum.modules.xmlutils.GeneralXMLParser import GeneralXMLParser
from Cerebrum.utils import aggregate

logger = logging.getLogger(__name__)


def parse_sp_participation(filename):
    """ parse study program participation from a merged persons file. """
    elements = []

    def handle_aktiv(data, stack):
        tag, attrs = stack[-1]
        elements.append((
            attrs['studieprogramkode'],
            attrs['arstall_kull'],
            attrs['studentnr_tildelt'],
        ))

    # GeneralXMLParser config: note that the xml tag stack must be a list
    parser_config = [(["data", "person", "aktiv"], handle_aktiv)]

    logger.info("reading study program participation from %s",
                repr(filename))
    GeneralXMLParser(parser_config, filename)
    logger.debug("found %d study program participation roles",
                 len(elements))
    return elements


def map_sp_student_ids(db, sp_triplets):
    pe = Factory.get('Person')(db)

    # Probably better to prepare a cache of studentnr -> person-id?
    for sp_code, sp_year, student_id in sp_triplets:
        pe.clear()
        try:
            pe.find_by_external_id(
                id_type=pe.const.externalid_studentnr,
                external_id=student_id,
                source_system=pe.const.system_fs,
            )
        except Errors.NotFoundError:
            logger.debug("unknown student id: %s", repr(student_id))
            continue

        yield (
            pe.entity_id,
            {
                'studieprogramkode': sp_code,
                'arstall_kull': sp_year,
            },
        )


def fetch_study_programs(db):
    """ Build study program participation cache. """
    filename = os.path.join(cereconf.FS_DATA_DIR, "merged_persons.xml")
    sp_triplets = parse_sp_participation(filename)
    data = aggregate.dict_collect_lists(map_sp_student_ids(db, sp_triplets))
    # sort data for a more consistent file cache
    for k in data.keys():
        data[k] = sorted(
            data[k],
            key=(lambda v: (v['arstall_kull'], v['studieprogramkode'])),
        )
    return data


class StudentStudyProgramCache(FileCache.JsonCache):
    """
    A cached mapping of person-id to study program participation.

    Typical use:
    ::

        def get_cache(db, max_age_hours=12):
            cache = StudentStudyProgramCache(
                db=db,
                max_age={'hours': max_age_hours},
            )
            return cache.data
    """

    name = 'fs-student-study-programs'
    build_callback = staticmethod(fetch_study_programs)
