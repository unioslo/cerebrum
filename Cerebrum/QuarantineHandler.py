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

"""This module decides how a quaratine should take effect by matching
rules in cereconf.QUARANTINE_RULES with the quarantines that an entity
is reported to have.  This is done by providing methods that can be
queried for the requested operation.

The format of cereconf.QUARANTINE_RULES is
  { <quarantine_code_str>: [ {  
         'lock': <0|1>,  'shell': <shell>, ....,
         'spread': spread_code|[spread_codes]
       } ] }

I.e, a dict of quarantine_code_str points to a list of dicts (for
backwards-compatibility, the list part may be skipped).

The 'spread' attribute in the inner dict is optinal.  If set, the
quarantine rule will only apply when the user has the spread in
question.  A spread value '*' or absence of spread attr matches any
spread.

The module will probably be expanded at a later time to allow for
ranking between quarantines etc.
"""

import cereconf
from Cerebrum import Entity
from Cerebrum.Constants import _QuarantineCode, _SpreadCode

class QuarantineHandler(object):
#    __slots__ = 'quarantines'

    qc2rules = {}
    def __init__(self, database, quarantines, spreads=None):
        """Constructs a QuarantineHandler.  quarantines should point
        to the quarantines that the user currently has.  Spreads is
        optional, and points to an optional list of spreads limiting
        the places where the QuarantineHandler will have effect.
        """
        if len(self.qc2rules) == 0:
            # Initial setup only done once.
            #
            # Converting strings to Constants and build:
            #
            # self.qc2rules = {'qc': {'spread_code': {settings} } }
            _QuarantineCode.sql = database
            _SpreadCode.sql = database
            for code, rules in cereconf.QUARANTINE_RULES.items():
                qc_rules = {}
                self.qc2rules[int(_QuarantineCode(code))] = qc_rules
                if isinstance(rules, dict):
                    rules = (rules,)
                for r in rules:
                    settings = r.copy()
                    if settings.has_key('spread'):
                        tmp_spreads = settings['spread']
                        del(settings['spread'])
                    else:
                        tmp_spreads = ('*',)
                    if isinstance(tmp_spreads, str):
                        tmp_spreads = (tmp_spreads,)
                    for c in tmp_spreads:
                        if c != '*':
                            c = int(_SpreadCode(c))
                        qc_rules[c] = settings
                        
        if quarantines is None:
            quarantines = []
        self.quarantines = quarantines
        if spreads is None:
            spreads = []
        self.spreads = [int(s) for s in spreads]
        # Append the '*' spread last to do the check against settings
        # for this spread last.
        self.spreads.append('*')

    def _get_matches(self):
        ret = []
        for q in self.quarantines:
            spread2settings = self.qc2rules[int(q)]
            # Note that for each spread, we only extract the first
            # matching setting.  Otherwise it would not be possible to
            # have a quarantine that did not lock the acount for a
            # spesific spread.
            for spread in self.spreads:
                if spread2settings.has_key(spread):
                    ret.append(spread2settings[spread])
                    break
        return ret

    def get_shell(self):
        for m in self._get_matches():
            shell = m.get('shell', None)
            if shell is not None:
                return shell
        return None
    
    def should_skip(self):
        for m in self._get_matches():
            if m.get('skip', 0):
                return 1
        return 0

    def is_locked(self):
        """The account should be known, but the account locked"""
        # Note that if any matching quaratine specifies lock, lock
        # will be used.
        for m in self._get_matches():
            if m.get('lock', 0):
                return 1
        return 0

    def check_entity_quarantines(db, entity_id, spreads=None):
        """Utility method that returns an initiated QuarantineHandler
        for a given entity_id"""
        eq = Entity.EntityQuarantine(db)
        eq.find(entity_id)
        return QuarantineHandler(
            db, [int(row['quarantine_type'])
                 for row in eq.get_entity_quarantine(only_active=True)],
            spreads)
    check_entity_quarantines = staticmethod(check_entity_quarantines)

def _test():
    # TODO: This should use the unit-testing framework, and use common
    # constants (which we currently don't have for spreads)    
    cereconf.QUARANTINE_RULES = {
        'nologin': {'lock': 1, 'shell': 'nologin-shell'},
        'system': [{'lock': 1, 'shell': 'nologin-shell'},
                   {'spread': 'AD_account', 'shell': 'ad-shell'}]
        }
    from Cerebrum.Utils import Factory
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)

    # Check with old cereconf syntax
    qh = QuarantineHandler(db, (co.quarantine_nologin,))
    print "nolgin: L=", qh.is_locked(), "S=", qh.get_shell()

    # New cereconf syntax, non-spread spesific
    qh = QuarantineHandler(db, (co.quarantine_system,))
    print "system: L=", qh.is_locked(), "S=", qh.get_shell()

    # spread-spesific quarantine action, should not be locked
    qh = QuarantineHandler(db, (co.quarantine_system,),
                           spreads=(co.spread_uio_ad_account,))
    print "system & AD: L=", qh.is_locked(), "S=", qh.get_shell()

    # spread-specific quarantine action and another quarantine that
    # requires lock
    qh = QuarantineHandler(db, (co.quarantine_system, co.quarantine_nologin),
                           spreads=(co.spread_uio_ad_account,))
    print "system & AD & L: L=", qh.is_locked(), "S=", qh.get_shell()

    qh = QuarantineHandler.check_entity_quarantines(db, 67201)
    print "An entity: L=", qh.is_locked(), "S=", qh.get_shell()

if __name__ == '__main__':
    _test()

# arch-tag: cfaaa1c8-a42d-4205-bb13-51dd9954ca8e
