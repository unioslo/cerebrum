#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# Copyright 2007 University of Oslo, Norway
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

"""Generate ldif files to populate VirtHome's LDAP tree.

This script can generate both user- and group LDIF files.
"""

import getopt
import sys

import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.Utils import simple_memoize
from Cerebrum.modules.LDIFutils import ldapconf
from Cerebrum.modules.LDIFutils import ldif_outfile
from Cerebrum.modules.LDIFutils import container_entry_string
from Cerebrum.modules.LDIFutils import entry_string
from Cerebrum.modules.LDIFutils import end_ldif_outfile
from Cerebrum import Errors



class LDIFHelper(object):
    """Utility class for common functionality in LDIF exports. 
    """


    def __init__(self):
        self.db = Factory.get("Database")()
        self.const = Factory.get("Constants")()

        # groups must be populated before users, since the latter relies on the
        # former due to data precaching.
        self.groups = self._load_groups()
        self.users = self._load_users()
    # end __init__


    def _uname2dn(self, uname):
        return ",".join(("uid=" + uname, ldapconf("USER", "dn")))
    # end _uname2dn


    def _gname2dn(self, gname):
        return ",".join(("cn=" + gname, ldapconf("GROUP", "dn")))
    # _gname2dn


    def _load_groups(self):
        """Cache a dict with group_id -> group_name for all LDAP-exportable
        groups. 

        See L{_load_users} for a related method.

        @rtype: dict (int -> dict-like object)
        @return:
          A dict mapping group_id to group info for all groups with
          LDAP-exportable spreads. The latter is controlled by
          cereconf.LDAP_GROUP.
        """

        group = Factory.get("Group")(self.db)
        spreads = tuple(self.const.human2constant(x)
                        for x in ldapconf("GROUP", "spreads", ()))
        logger.debug("Collecting groups for LDAP export. "
                     "Spreads: %s", ", ".join(str(x) for x in spreads))
        return dict((x["group_id"], x)
                    for x in group.search(spread=spreads))
    # end _load_groups
    

    def _load_users(self):
        """Cache enough user information for the export to progress."""


        account = Factory.get("Account")(self.db)
        spreads = tuple(self.const.human2constant(x)
                        for x in ldapconf("USER", "spreads", ()))
        logger.debug("Collecting users for LDAP export. "
                     "Spreads: %s", ", ".join(str(x) for x in spreads))
        users = dict()
        account = Factory.get("Account")(self.db)
        for spread in spreads:
            for row in account.search(spread=spread):
                users[row["account_id"]] = {"uname": row["name"],
                                            "np_type": row["np_type"],}

        users = self._get_contact_info(users)
        users = self._get_password_info(users)
        users = self._get_membership_info(users)
        return users
    # end _load_users


    def _get_contact_info(self, users):
        """Update users with name and e-mail data."""


        def _mangle(account_id, contact_type, contact_value, users):
            if contact_type not in (self.const.human_first_name, 
                                    self.const.human_last_name,
                                    self.const.human_full_name):
                return contact_value

            account_type = users.get(account_id, {}).get("np_type")
            if account_type == self.const.virtaccount_type:
                return contact_value + " (unverified)"

            return contact_value
        # end _mangle
        
        account = Factory.get("Account")(self.db)
        contact2tag = {self.const.virthome_contact_email: "email",
                       self.const.human_first_name: "givenName",
                       self.const.human_last_name: "sn",
                       self.const.human_full_name: "cn",}
                
        logger.debug("Collecting email/name info for LDAP export")
        for eci in account.list_contact_info(
                       source_system=self.const.system_virthome,
                       contact_type=tuple(contact2tag)):
            account_id = eci["entity_id"]
            if account_id not in users:
                continue

            contact_type = int(eci["contact_type"])
            contact_value = _mangle(account_id, contact_type,
                                    eci["contact_value"], users)
            tag = contact2tag[contact_type]
            users[account_id][tag] = contact_value
            
        return users
    # end _get_contact_info


    def _get_password_info(self, users):
        """Collect md5 hashes for VA-s."""

        logger.debug("Collecting password information")
        account = Factory.get("Account")(self.db)
        for row in account.list_account_authentication(
                              auth_type=self.const.auth_type_md5_crypt):
            account_id = row["account_id"]
            if account_id not in users:
                continue

            if users[account_id]["np_type"] != self.const.virtaccount_type:
                continue
            
            users[account_id]["userPassword"] = (row["auth_data"],)
        return users
    # end _get_password_info


    def _get_membership_info(self, users):
        """Collect group memberships information."""
        
        group = Factory.get("Group")(self.db)
        logger.debug("Collecting user membership information")

        # crap. this is going to be VERY expensive...
        for row in group.search_members(member_type=self.const.entity_account):
            group_id = row["group_id"]
            if group_id not in self.groups:
                continue

            account_id = row["member_id"]
            if account_id not in users:
                continue

            gname = self._gname2dn(self.groups[group_id]["name"])
            users[account_id].setdefault("membership", list()).append(gname)
        return users
    # end _get_membership_info


    def yield_groups(self):
        """Generate group dicts with all LDAP-relevant information.
        """

        group = Factory.get("Group")(self.db)
        for group_id in self.groups:
            gi = self.groups[group_id]
            group_name = gi["name"]
            entry = {"dn": (self._gname2dn(group_name),),
                     "cn": (group_name,),
                     "objectClass": ldapconf("GROUP", "objectClass"),
                     "description": (gi["description"],),}
            entry.update(self._get_member_info(group_id, group))
            yield entry
    # end _extend_group_information


    def _get_member_info(self, group_id, group):
        """Retrieve all members of a group.

        We need to respect LDAP-spreads for users and groups alike.

        @rtype: dict (str -> sequence of DNs)
        @return:
          A dict with one entry, 'member' -> sequence of members in the
          respective group.
        """

        # TBD: Maybe this ought to be cached? 
        members = tuple(self._uname2dn(self.users[x["member_id"]]["uname"])
                                for x in group.search_members(group_id=group_id)
                                if x["member_id"] in self.users)
        if members:
            return {"member": members}
        return {}
    # end _get_member_info


    def yield_users(self):
        """Yield all users qualified for export to LDAP."""

        def _mangle(attrs):
            if not isinstance(attrs, (list, set, tuple)):
                return (attrs,)
            return attrs
        
        for user_id in self.users:
            attrs = self.users[user_id]
            tmp = {"dn": (self._uname2dn(attrs["uname"]),),
                   "uid": (attrs["uname"],),
                   "email": (attrs["email"],),
                   "objectClass": ldapconf("USER", "objectClass"),}

            for key in ("cn", "sn", "givenName", "userPassword", "membership",):
                if key in attrs:
                    tmp[key] = _mangle(attrs[key])

            yield tmp
    # end generate_users
# end UserLDIF



def generate_all(fname):
    """Generate user + group LDIF to fname. """

    logger.debug("Generating ldif into %s", fname)

    out = ldif_outfile("ORG", fname)

    out.write(container_entry_string("ORG"))

    helper = LDIFHelper()
    out.write(container_entry_string("USER"))
    for user in helper.yield_users():
        dn = user["dn"][0]
        del user["dn"]
        out.write(entry_string(dn, user, False))
    end_ldif_outfile("USER", out, out)

    logger.debug("Generating group ldif...")
    out.write(container_entry_string("GROUP"))
    for group in helper.yield_groups():
        dn = group["dn"][0]
        del group["dn"]
        out.write(entry_string(dn, group, False))

    end_ldif_outfile("GROUP", out)
    logger.debug("Done with group ldif (all done)")
# end generate_all
    


def main(argv):
    opts, junk = getopt.getopt(argv[1:],
                               "f:",
                               ("file=",))


    filename = None
    for option, value in opts:
        if option in ('-f', '--file',):
            filename = value

    if filename:
        generate_all(filename)
# end main


    
logger = Factory.get_logger("cronjob")
if __name__ == "__main__":
    main(sys.argv[:])
