# Copyright 2002, 2003 University of Oslo, Norway

import xml.sax
import re
from Cerebrum import Group
from Cerebrum.Constants import _SpreadCode

import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory

from Cerebrum import Disk
import pprint
pp = pprint.PrettyPrinter(indent=4)

class LookupHelper(object):
    def __init__(self, db):
        self._db = db
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
            print "WARNING: bad spread: %s" % name
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
            print "WARNING: ukjent gruppe: %s" % name
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
            print "ukjent sko: %s" % name
        return self._sko_cache[name]
