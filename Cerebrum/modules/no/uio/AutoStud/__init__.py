# -*- coding: iso-8859-1 -*-
"""This is the only class that should be directly accessed within
this package"""

import re

import cereconf

from Cerebrum.modules.no.uio.AutoStud import ProfileConfig
from Cerebrum.modules.no.uio.AutoStud import ProfileHandler
from Cerebrum.modules.no.uio.AutoStud import StudentInfo
from Cerebrum import Disk

class AutoStud(object):
    def __init__(self, db, logger, cfg_file=None, debug=0,
                 studieprogs_file=None, emne_info_file=None):
        self._logger = logger
        self.debug = debug
        self.db = db
        self.disks = {}
        self.disks_order = []
        if True:
            disk = Disk.Disk(db)
            for d in disk.list():
                self.disks[int(d['disk_id'])] = [d['path'], int(d['count'])]
            self.disks_order = self.disks.keys()
            self.disks_order.sort(self._disk_sort)
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
        return cmp(int(num_x), int(num_y))

    def start_student_callbacks(self, student_file, callback_func):
        StudentInfo.StudentInfoParser(student_file, callback_func, self._logger)

    def get_profile(self, student_info, groups=None):
        """Returns a Profile object matching the topics, to check
        quotas, groups must also be set."""
        return ProfileHandler.Profile(student_info, self._logger, self.pc,
                                      groups=groups)
