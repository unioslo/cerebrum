#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2009 University of Oslo, Norway
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

# Clean out manually registered affiliation if an equivalent affiliation
# has been registered by an authoritative system.

import cerebrum_path
from Cerebrum import Utils
import cereconf


Factory = Utils.Factory
db = Factory.get('Database')()
co = Factory.get('Constants')(db)
db.cl_init(change_program='auto_ldap')
acc=Factory.get("Account")(db)
pu=Factory.get("PosixUser")(db)
person=Factory.get("Person")(db)
logger = Factory.get_logger("console")

#spread=co.spread_ntnu_ldap_user
spread=co.spread_ntnu_ldap_user

preferred_home = {
    co.affiliation_ansatt: [
        co.spread_ntnu_ansatt_user,
        co.spread_ntnu_stud_user,
        ],
    co.affiliation_student: [
        co.spread_ntnu_stud_user,
        co.spread_ntnu_ansatt_user,
        ],
    None: [
        co.spread_ntnu_ansatt_user,
        co.spread_ntnu_stud_user,
        ],
    }

def expand_preferred_home():
    r={}
    for aff, spreads in cereconf.LDAP_PREFERRED_HOME.items():
        if aff=='*':
            aff=None
        else:
            aff=co.PersonAffiliation(aff)
        r[aff] = [co.Spread(s) for s in spreads]
    return r

preferred_home = expand_preferred_home()


def auto_ldap_spread():
    homes={}
    for h in acc.list_account_home():
        if not homes.has_key(h["account_id"]):
            homes[h["account_id"]]={}
        homes[h["account_id"]][h["home_spread"]]=h["homedir_id"]

    hasspread=set()
    for u in pu.list_all_with_spread(spread):
        hasspread.add(u["entity_id"])

    affs={}
    for a in acc.list_accounts_by_type():
        affs.setdefault(a['account_id'], []).append((a['affiliation'], 
                                                           a['priority']))
    

    for u in pu.list_posix_users():
        if not u["account_id"] in hasspread:
            logger.info("Adding spread %d for account %d",
                        spread, u["account_id"])
            acc.clear()
            acc.find(u["account_id"])
            acc.add_spread(spread)

        paff=None
        saffs=sorted(affs.get(u["account_id"], []),
                     cmp=lambda x,y: cmp(x[1],y[1]))
        if len(saffs)>0:
            paff=saffs[0]

        homedir=None
        preferred_homes = (preferred_home.get(paff) or
                           preferred_home.get(None, []))
        for s in preferred_homes:
            if homes.get(u["account_id"], {}).has_key(s):
                homedir=homes[u["account_id"]][s]
                break
        ohomedir=homes.get(u["account_id"], {}).get(spread)
        
        if ohomedir != homedir:
            logger.info("Setting homedir for account %d, spread %d to %s",
                        u["account_id"], spread, homedir)
            acc.clear()
            acc.find(u["account_id"])
            acc.set_home(spread, homedir)
        db.commit()


if __name__ == '__main__':
    auto_ldap_spread()
