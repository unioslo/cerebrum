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
from time import localtime, strftime, time
import pprint
import sys

import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.Constants import _SpreadCode

class LookupHelper(object):
    def __init__(self, db, logger, ou_perspective):
        self._db = db
        self._logger = logger
        self.spread_name2const = {}
        self._group_cache = {}
        self._sko_cache = {}
        self._ou_perspective = ou_perspective

        self.const = Factory.get('Constants')(self._db)
        for c in dir(self.const):
            const = getattr(self.const, c)
            if isinstance(const, _SpreadCode):
                self.spread_name2const[str(const)] = const
        self._cached_affiliations = [None]

    def get_spread(self, name):
        try:
            return self.spread_name2const[name]
        except KeyError:
            self._logger.warn("bad spread: %s" % name)
            return None

    def get_group(self, name):
        if self._group_cache.has_key(name):
            return self._group_cache[name] 
        group = Factory.get('Group')(self._db)
        group.clear()
        try:
            group.find_by_name(name)
            self._group_cache[name] = int(group.entity_id)
        except (Errors.NotFoundError, ValueError):
            self._group_cache[name] = None
            self._logger.warn("ukjent gruppe: %s" % name)
        return self._group_cache[name] 

    def get_stedkode(self, name, institusjon):
        if self._sko_cache.has_key(name):
            return self._sko_cache[name]
        try:
            ou = Factory.get('OU')(self._db)
            fak = int(name[:2])
            inst = int(name[2:4])
            gr = int(name[4:])
            ou.clear()
            ou.find_stedkode(fak, inst, gr, institusjon)
            self._sko_cache[name] = int(ou.entity_id)
        except (Errors.NotFoundError, ValueError):
            self._sko_cache[name] = None
            self._logger.warn("ukjent sko: %s" % name)
        return self._sko_cache[name]

    def get_all_child_sko(self, sko):
        ret = []
        ou = Factory.get('OU')(self._db)
        ou.find(sko)
        ret.append("%02i%02i%02i" % (
            ou.fakultet, ou.institutt, ou.avdeling))
        for row in ou.list_children(self._ou_perspective, recursive=True):
            ou.clear()
            ou.find(row['ou_id'])
            ret.append("%02i%02i%02i" % (
                ou.fakultet, ou.institutt, ou.avdeling))
        return ret

    def get_person_affiliations(self, fnr=None, person_id=None):
        # We only need to cache the last entry as input is sorted by fnr
        if self._cached_affiliations[0] is None or (
            not (self._cached_affiliations[0] in (fnr, person_id))):
            person = Factory.get('Person')(self._db)
            if fnr is not None:
                person.find_by_external_id(self.const.externalid_fodselsnr,
                                           fnr, source_system=self.const.system_fs)
            else:
                person.find(person_id)
            ret = []
            for row in person.get_affiliations():
                ret.append({
                    'ou_id': int(row['ou_id']),
                    'affiliation': int(row['affiliation']),
                    'status': int(row['status'])})
            if fnr is None:
                self._cached_affiliations = (fnr, ret)
            else:
                self._cached_affiliations = (person_id, ret)                
        return self._cached_affiliations[1]

class ProgressReporter(object):
    """Logging framework the makes log-files somewhat easier to read
    (set_indent method).  A future version might make this a wrapper
    to the standard logging module."""

    DEBUG2=7
    DEBUG=6
    INFO=5
    INFO2=4
    WARN=3
    ERROR=2
    
    def __init__(self, logfile, stdout=False, loglevel=DEBUG2):
        self.stdout = stdout
        if stdout:
            self.out = sys.stdout
        else:
            self.out = open(logfile, 'w')
        self.prev_msgtime = time()
        self.pp = pprint.PrettyPrinter(indent=4)
        self.indent = 0
        self.loglevel = loglevel

    def set_indent(self, val):
        self.indent = val

    def _log(self, msg, append_newline):
        out = ''
        for line in msg.split("\n"):
            out += "%s%s\n" % (" " * self.indent, line)
        out = out[:-1]
        if append_newline:
            out += "\n"
        self.out.write(out)
        self.out.flush()

    def debug(self, msg, append_newline=True):
        if self.DEBUG <= self.loglevel:
            self._log(msg, append_newline)

    def debug2(self, msg, append_newline=True):
        if self.DEBUG2 <= self.loglevel:
            self._log(msg, append_newline)

    def info(self, msg, append_newline=True):
        if self.INFO > self.loglevel:
            return
        now = time()
        self._log("[%s] %s (delta: %i)" % (strftime("%H:%M:%S", localtime()),
                                           msg, now - self.prev_msgtime),
                  append_newline)
        self.prev_msgtime = now

    def info2(self, msg, append_newline=True):
        if self.INFO2 <= self.loglevel:
            self._log(msg, append_newline)

    def warn(self, msg, append_newline=True):
        if self.WARN <= self.loglevel:
            self._log("WARNING: %s" % msg, append_newline)

    def error(self, msg, append_newline=True):
        if self.ERROR <= self.loglevel:
            self._log(msg, append_newline)

    def pformat(self, obj):
        return self.pp.pformat(obj)

    def __del__(self):
        if not self.stdout:
            self.out.close()
