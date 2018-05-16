# -*- coding: utf-8 -*-
# Copyright 2005 University of Oslo, Norway
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

# TBD: Provide defaults for all settings like cereconf?
# from Cerebrum.default_config import *

CLASS_BATCH = ['Cerebrum.modules.process_entity.ProcBatchRunner/ProcBatchRunner',]
CLASS_HANDLER = ['Cerebrum.modules.process_entity.ProcHandler/ProcHandler',]


# authoritative source system for Cerebrum-data
SOURCE={'source_system': 'EKSTENS'}

# What methods should be called by the ProcBatchRunner
# The four listed below are what's supported now
PROC_METHODS= ('process_persons',
               'process_groups',
               'process_OUs',
               'process_account_types')

# What spreads different entities should get
PERSON_SPREADS = ('person@ldap',)
OU_SPREADS = ('ou@ad',)
SHADOW_GROUP_SPREAD = ('group@ad', 'group@oid')
AC_TYPE_GROUP_SPREAD = ('group@ad')

# Spread handling. You have to select one of ACCOUNT_SPREADS or
# OU2ACCOUNT_SPREADS. You cannot have both.

# Dict of 'affiliation' -> 'spread' mappings. process_entity will
# make a union if an account has two or more affiliations.
ACCOUNT_SPREADS = {'ANSATT': ('account@lms', 'account@oid'),
                   'ELEV': ('account@lms', 'account@oid'),
                   'AFFILIATE': () }
# What trait should an external id of a given type result in for a
# shadow group
GRP_TYPE_TO_GRP_TRAIT = {'kl-ID': 'kls_group'}

# Enabling OU2ACCOUNT_SPREADS means that an account's spreads is
# calculated from what spreads the OUs in account_types have. Three
# OUs with three separate spreads and one account with account_type to
# all three means the account gets all three spreads.
OU2ACCOUNT_SPREADS = {'ou@ad' : 'account@ad',
                      'ou@lms' : 'account@lms',
                      'ou@ldap' : 'account@ldap'}

# Handle the name of shadow_groups. Shadow groups are groups created
# from groups already present in Cerebrum, tagged with
# co.trait_group_imported. These groups have persons as members and we
# want to make a dynamic version populated with the accounts of these
# people(if present). The following code determines the name of the
# 'shadow group'.
#
# Simple example tagging these groups with "cerebrum_groupname"
SHADOW = lambda x: "cerebrum_%s" % x
#
# Give ProcBatchRunner the name of the normal group
def NORMAL(x):
    import re
    m = re.search("^cerebrum_(.+)$", x)
    if not m:
        return None
    return m.group(1)
#
# More complex example that can return None to signal errors
def SHADOW(x): 
    import re
    m = re.search("^(\w+):(\d\d):(.+)", x)
    if not m:
        return None
    return "%s:%s" % (m.group(1),m.group(3))

def NORMAL(x):
    import re
    from mx import DateTime
    m = re.search("^(\w+):(.+)", x)
    if not m:
        return None
    now = DateTime.now()
    year = str(now.year)
    year = year[2:]
    if now.month < 7:
        year = int(year) - 1
    year = int(year)
    return "%s:%.2d:%s" % (m.group(1),year,m.group(2))
