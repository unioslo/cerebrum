# Copyright 2002 University of Oslo, Norway
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

"""The ADUser module is used as a mixin-class for Account, and
contains additional parameters that are required for building Accounts in
Active Directory.  This includes the OU(as defined in AD) a group or user is
connected to. The ADUser also got to new values defined, login script and
home directory.

The user name is inherited from the superclass, which here is Entity."""

import string
import cereconf
from Cerebrum import Utils
from Cerebrum import Constants, Errors
from Cerebrum.Entity import Entity, EntityName, EntityQuarantine
from Cerebrum.Utils import Factory

Cerebrum = Factory.get('Database')()
co = Factory.get('Constants')(Cerebrum)

#print 'hei:',int(co.entity_account)


class ADObject(EntityName, EntityQuarantine, Entity):
# Bare arve egenskaper fra Entity?

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('ou_id',)

    def clear(self):
        self.__super.clear()
        for attr in ADObject.__read_attr__:
            if hasattr(self, attr):
                delattr(self, attr)
        for attr in ADObject.__write_attr__:
            setattr(self, attr, None)
        self.__updated = False

    def __eq__(self, other):
        assert isinstance(other, ADObject)
        if self.ou_id   == other.ou_id:
            return self.__super.__eq__(other)
        return False

    def get_all_ad_users(self):
        "get all users in the ad table"
        return self.query("""
        SELECT entity_id,ou_id
        FROM [:table schema=cerebrum name=ad_entity]
        WHERE entity_type=2003""")



#
# Andre metoder.
# def find
# def find_ad_groups
# def find_ad_ous
# def find_ad_users finnes i aduser modulen.
# def populate.
#
# Antar alle skal til ad inntil spread er ferdig.
# har ingen quick sync funksjoner enda....
#
# Finne en Account sin Person, hører til ADUser
# Finne account locked status, hentes fra quarantine? 
#
#TODO: diverse metoder: find, populate?, write_db,
#      get_ad_users- finne alle ad brukere med status, skal hente verdier som
#      account locked, default verdi for hjemmeområde og loginscript,
#      full name og user_name. 
#      get_ad_user- samme som over, men for en account, til bruk i quick sync.
#          



