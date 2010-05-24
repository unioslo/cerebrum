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

        self.users = self._load_users()
        self.groups = self._load_groups()
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
        """Cache a dict with account_id -> account_name for all
        LDAP-exportable accounts.

        We probably want to carry these around in memory all the time, since
        both user AND group exports require lists of DNs (group/user names, at
        least) for entities with the right spread. There is no getting around
        this, unless paying the clear() + find() penalty for _each_ entry is
        acceptable later.

        @rtype: dict (int -> str)
        @return:
          A dict mapping account_id to account_name for all accounts with
          LDAP-exportable spreads. The latter is controlled by
          cereconf.LDAP_USER.
        """

        account = Factory.get("Account")(self.db)
        spreads = tuple(self.const.human2constant(x)
                        for x in ldapconf("USER", "spreads", ()))
        logger.debug("Collecting users for LDAP export. "
                     "Spreads: %s", ", ".join(str(x) for x in spreads))
        users = dict()
        account = Factory.get("Account")(self.db)
        for spread in spreads:
            for row in account.search(spread=spread):
                users[row["account_id"]] = row["name"]

        return users
    # end generate_users
# end LDIFHelper



class GroupLDIF(LDIFHelper):
    """LDIF generator for VirtHome groups.
    """

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
            entry.update(self._get_membership_info(group_id, group))
            yield entry
    # end _extend_group_information


    def _get_membership_info(self, group_id, group):
        """Retrieve all members of a group.

        We need to respect LDAP-spreads for users and groups alike.

        @rtype: dict (str -> sequence of DNs)
        @return:
          A dict with one entry, 'member' -> sequence of members in the
          respective group.
        """

        members = tuple(self._uname2dn(self.users[x["member_id"]])
                                for x in group.search_members(group_id=group_id)
                                if x["member_id"] in self.users)
        if members:
            return {"member": members}
        return {}
    # end _get_membership_info
# end GroupLDIF
    


class UserLDIF(LDIFHelper):
    """LDIF generator for VirtHome users.
    """

    def yield_users(self):
        """Yield all users qualified for export to LDAP.
        """

        for user_id in self.users:
            uname = self.users[user_id]
            yield self._extend_user_information(user_id, uname)
    # end generate_users


    def _extend_user_information(self, user_id, uname):
        """Return a dict with all of user's relevant LDAP information.

        @rtype: dict (str -> sequence of str)
        @return:
          A dict mapping LDIF attributes to their respective values.
        """

        account = Factory.get("Account")(self.db)
        account.find(user_id)
                
        entry = {"dn": (self._uname2dn(uname),),
                 "uid": (uname,),
                 "email": (account.get_email_address(),),
                 "objectClass": ldapconf("USER", "objectClass"),}
        entry.update(self._get_user_names(account))
        entry.update(self._get_password_info(account))
        entry.update(self._get_membership_info(account))
        return entry
    # end extend_user_information


    def _get_membership_info(self, account):
        """Retrieve all group memberships for account.
        
        We fetch _ONLY_ the groups possessing a certain spread (see _gid2dn).
        """

        group = Factory.get("Group")(self.db)
        memberships = tuple(self._gname2dn(x["name"])
                            for x in group.search(member_id=account.entity_id)
                            if x["group_id"] in self.groups)
        if memberships:
            return {"membership": memberships}
        return {}
    # end _get_membership_info



    def _get_password_info(self, account):
        """Retrieve password information for account.

        Since we store passwords for VAs only, they are the only kind of
        accounts for which we actually /can/ return password hashes.
        """

        if account.np_type != self.const.virtaccount_type:
            return {}

        try:
            crypt = account.get_account_authentication(
                               self.const.auth_type_md5_crypt)
            return {"userPassword": (crypt,)}
        except Errors.NotFoundError:
            logger.warn("VA %s (id=%s) is missing auth info (%s)",
                        account.account_name, account.entity_id,
                        str(self.const.auth_type_md5_crypt))
            return {}
    # end _get_password_info
        


    def _get_user_names(self, account):
        """Retrieve all names pertinent to the specified account.

        @param account: Account-proxy associated with the proper account.
        """

        const = self.const
        def mangler(name):
            """Re-write all names, since export to LDAP _must_ mark
            non-federated accounts as 'untrusted'.
            """

            # FIXME: is this an error?
            if not name or not name.strip():
                return "(not available)"

            if account.np_type == const.virtaccount_type:
                return name + " (unverified)"

            return name
        # end name_mangler

        names = dict()
        names["cn"] = (mangler(account.get_owner_name(const.human_full_name)),)
        names["sn"] = (mangler(account.get_owner_name(const.human_last_name)),)
        names["givenName"] = (mangler(account.get_owner_name(const.human_first_name)),)
        return names
    # end _get_user_names
# end UserLDIF



def generate_user_ldif(fname):
    """Output all users matching the LDIF criteria.
    """

    logger.debug("Generating user ldif into %s", fname)
    out = ldif_outfile("USER", fname)
    userldif = UserLDIF()
    out.write(container_entry_string("USER"))
    for user in userldif.yield_users():
        dn = user["dn"][0]
        del user["dn"]
        out.write(entry_string(dn, user, False))

    end_ldif_outfile("USER", out)
# end generate_user_ldif



def generate_group_ldif(fname):
    """Output all groups matching the LDIF criteria.
    """

    logger.debug("Generating group ldif into %s", fname)
    out = ldif_outfile("GROUP", fname)
    groupldif = GroupLDIF()
    out.write(container_entry_string("GROUP"))
    for group in groupldif.yield_groups():
        dn = group["dn"][0]
        del group["dn"]
        out.write(entry_string(dn, group, False))

    end_ldif_outfile("GROUP", out)
# end generate_group_ldif



def main(argv):
    opts, junk = getopt.getopt(argv[1:],
                               "u:g:",
                               ("user-file=",
                                "userfile=",
                                "user_file=",
                                "group-file=",
                                "groupfile=",
                                "group_file=",))

    user_file = None
    group_file = None
    for option, value in opts:
        if option in ('-u', '--user-file', "--userfile", "--user_file",):
            user_file = value
        elif option in ('-g', '--group-file', "--groupfile", "--group_file",):
            group_file = value

    if user_file:
        generate_user_ldif(user_file)
    if group_file:
        generate_group_ldif(group_file)
# end main


    
logger = Factory.get_logger("cronjob")
if __name__ == "__main__":
    main(sys.argv[:])
