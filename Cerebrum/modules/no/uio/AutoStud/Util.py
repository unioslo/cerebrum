# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway

import xml.sax
from time import gmtime, strftime, time
import pprint
import sys

import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.Constants import _SpreadCode
from Cerebrum import Group

class LookupHelper(object):
    def __init__(self, db, logger):
        self._db = db
        self._logger = logger
        self.spread_name2const = {}
        self._group_cache = {}
        self._sko_cache = {}

        self.const = Factory.get('Constants')(self._db)
        for c in dir(self.const):
            const = getattr(self.const, c)
            if isinstance(const, _SpreadCode):
                self.spread_name2const[str(const)] = const

    def get_spread(self, name):
        try:
            return self.spread_name2const[name]
        except KeyError:
            self._logger.warn("bad spread: %s" % name)
            return None

    def get_group(self, name):
        if self._group_cache.has_key(name):
            return self._group_cache[name] 
        group = Group.Group(self._db)
        group.clear()
        try:
            group.find_by_name(name)
            self._group_cache[name] = int(group.entity_id)
        except (Errors.NotFoundError, ValueError):
            self._group_cache[name] = None
            self._logger.warn("ukjent gruppe: %s" % name)
        return self._group_cache[name] 

    def get_stedkode(self, name):
        #TODO: not quite right, remove once xml file is fixed
        name = name.replace("SV-student", "140000")
        name = name.replace("UV-student", "140000")
        name = name.replace("Jus-student", "140000")
        name = name.replace("MNF-student", "140000")
        name = name.replace("S", "0")
        if(int(name) > 300000):
            name = "140000"
        if self._sko_cache.has_key(name):
            return self._sko_cache[name]
        try:
            ou = Factory.get('OU')(self._db)
            fak = int(name[:2])
            inst = int(name[2:4])
            gr = int(name[4:])
            ou.clear()
            ou.find_stedkode(fak, inst, gr)
            self._sko_cache[name] = int(ou.entity_id)
        except (Errors.NotFoundError, ValueError):
            self._sko_cache[name] = None
            self._logger.warn("ukjent sko: %s" % name)
        return self._sko_cache[name]

class ProgressReporter(object):
    """Logging framework the makes log-files somewhat easier to read
    (set_indent method).  A future version might make this a wrapper
    to the standard logging module."""

    def __init__(self, logfile, stdout=0):
        self.stdout = stdout
        if stdout:
            self.out = sys.stdout
        else:
            self.out = open(logfile, 'w')
        self.prev_msgtime = time()
        self.pp = pprint.PrettyPrinter(indent=4)
        self.indent = 0

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

    def debug(self, msg, append_newline=1):
        self._log(msg, append_newline)

    def debug2(self, msg, append_newline=1):
        self._log(msg, append_newline)

    def info(self, msg, append_newline=1):
        self._log("[%s] %s (delta: %i)" % (strftime("%H:%M:%S", gmtime()), msg,
                                           (time()-self.prev_msgtime)), append_newline)
        self.prev_msgtime = time()

    def info2(self, msg, append_newline=1):
        self._log(msg, append_newline)

    def warn(self, msg, append_newline=1):
        self._log("WARNING: %s" % msg, append_newline)

    def error(self, msg, append_newline=1):
        self._log(msg, append_newline)

    def pformat(self, obj):
        return self.pp.pformat(obj)

    def __del__(self):
        if not self.stdout:
            self.out.close()
