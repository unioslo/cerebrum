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

"""This is the only class that should be directly accessed within
this package"""

import re

import cereconf
from Cerebrum.Utils import Factory

from Cerebrum.modules.no.uio.AutoStud import ProfileConfig
from Cerebrum.modules.no.uio.AutoStud import ProfileHandler
from Cerebrum.modules.no.uio.AutoStud import StudentInfo

class AutoStud(object):
    def __init__(self, db, logger, cfg_file=None, debug=0,
                 studieprogs_file=None, emne_info_file=None,
                 ou_perspective=None):
        self._logger = logger
        self.debug = debug
        self.db = db
        self.disks = {}
        self.disks_order = []
        self.student_disk = {}
        self.co = Factory.get('Constants')(db)
        if not ou_perspective:
            self.ou_perspective = self.co.perspective_fs
        else:
            self.ou_perspective = ou_perspective
        if True:
            disk = Factory.get('Disk')(db)
            for d in disk.list(filter_expired=True, spread=getattr(self.co, cereconf.HOME_SPREADS[0])):
                self.disks[int(d['disk_id'])] = [d['path'], int(d['count'])]
            self.disks_order = self.disks.keys()
            self.disks_order.sort(self._disk_sort)
            logger.debug("Disks: "+logger.pformat(self.disks))
        self.pc = ProfileConfig.Config(self, logger, debug=debug, cfg_file=cfg_file)
        logger.debug(self.pc.debug_dump())
        self.studieprogramkode2info = {}
        for sp in StudentInfo.StudieprogDefParser(studieprogs_file=studieprogs_file):
            self.studieprogramkode2info[sp['studieprogramkode']] = sp
        self.emnekode2info = {}
        for emne in StudentInfo.EmneDefParser(emne_info_file):
            self.emnekode2info[emne['emnekode']] = emne

    def _disk_sort(self, x, y):
        regexp = re.compile(r"^(\D+)(\d*)")
        m_x = regexp.match(self.disks[x][0])
        m_y = regexp.match(self.disks[y][0])
        pre_x, num_x = m_x.group(1), m_x.group(2)
        pre_y, num_y = m_y.group(1), m_y.group(2)
        if pre_x <> pre_y:
            return cmp(pre_x, pre_y)
        try:
            return cmp(int(num_x), int(num_y))
        except ValueError:
            self._logger.warn("Unexpected disk name %s or %s" % (
                              self.disks[x][0], self.disks[y][0]))
            return cmp(pre_x, pre_y)

    def start_student_callbacks(self, student_file, callback_func):
        StudentInfo.StudentInfoParser(student_file, callback_func, self._logger)

    def get_profile(self, student_info, member_groups=None):
        """Returns a Profile object matching the topics, to check
        quotas, groups must also be set."""
        return ProfileHandler.Profile(student_info, self._logger, self.pc,
                                      member_groups=member_groups)
