# Copyright 2002, 2003 University of Oslo, Norway
#
# This file is part of Cerebrum.

"""This module decides how a quaratine should take effect by matching
rules in cereconf.QUARANTINE_RULES with the quarantines that an entity
is reported to have.  This is done by providing methods that can be
queried for the requested operation.

The format of cereconf.QUARANTINE_RULES is
  { <quarantine_code_str>: {'lock': <0|1>,  'shell': <shell>, .... },
    ... }

The module will probably be expanded at a later time to allow for
ranking between quarantines etc.
"""

import cereconf
from Cerebrum.Constants import _QuarantineCode

class QuarantineHandler(object):
    rules = {}
    def __init__(self, database, quarantines):
        if len(self.rules) == 0:
            _QuarantineCode.sql = database
            for k in cereconf.QUARANTINE_RULES.keys():
                qc = _QuarantineCode(k)
                self.rules[int(qc)] = cereconf.QUARANTINE_RULES[k]
        if quarantines is None:
            quarantines = []
        self.quarantines = quarantines

    def get_shell(self):
        for q in self.quarantines:
            shell = self.rules[int(q)].get('shell', None)
            if shell is not None:
                return shell
        return None
    
    def should_skip(self):
        for q in self.quarantines:
            if self.rules[int(q)].get('skip', 0):
                return 1
        return 0

    def is_locked(self):
        for q in self.quarantines:
            if self.rules[int(q)].get('lock', 0):
                return 1
        return 0

