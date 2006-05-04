#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
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

""" Module for guests and other temporary users in Cerebrum

The module contains functionality for handling guests and other
temporary users.

"""

from mx import DateTime

import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory, NotSet
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.modules.PosixUser import PosixUser


class GuestAccountException(Exception):
    """General exception for GuestAccount"""
    pass


class BofhdUtils(object):
    def __init__(self, server):
        self.server = server
        self.db = server.db
        self.co = Factory.get('Constants')(self.db)
        self.logger = server.logger

    def request_guest_users(self, num, end_date, comment,
                            owner_type, owner_id, operator_id):
        """Reserve num guest users until they're manually released or
        until end_date. If the function fails because there are not
        enough guest users available, GuestAccountException is raised.

        """
        if num > self.num_available_accounts():
            raise GuestAccountException, ("Not enough available guest users.\n"
                                          "Use 'user guests_status' to find "
                                          "the number of available guests.")
        ret = []
        for guest in self._find_guests(num):
            e_id, passwd = self._alloc_guest(guest, end_date, comment,
                                             owner_type, owner_id, operator_id)
            ret.append((guest, comment, e_id, passwd))
        return ret

    def release_guest(self, guest, operator_id):
        """Release a guest account from temporary owner.

        Make sure that the guest account specified actually exists and
        release it from owner. The guest account is now in
        release_quarantine and will be available for new allocations
        when the quarantine period is due.
        
        """
        ac = Factory.get('Account')(self.db)
        ac.find_by_name(guest)
        trait = ac.get_trait(self.co.trait_guest_owner)
        if trait is None:
            raise GuestAccountException("%s is not a guest" % guest)
        elif trait['target_id'] is None:
            raise GuestAccountException("%s is already available" % guest)
        # Remove owner, i.e set owner_trait to None
        ac.populate_trait(self.co.trait_guest_owner, target_id=None)
        self.logger.debug("Removed owner_id in owner_trait for %s" % guest)
        # Remove quarantine set by _alloc_guest and set a new
        # quarantine that kicks in now.
        if ac.get_entity_quarantine(self.co.quarantine_guest_release):
            ac.delete_entity_quarantine(self.co.quarantine_guest_release)
        ac.add_entity_quarantine(self.co.quarantine_guest_release, operator_id,
                                 "Guest user released", start=DateTime.today())
        self.logger.debug("%s is now in release_quarantine" % guest)
        ac.set_password(ac.make_passwd(guest))
        ac.write_db()
        self.update_group_memberships(ac.entity_id)
        self.logger.debug("Updating group memberships for %s" % guest)
        # Finally, register a request to archive the home directory.
        # A new directory will be created when archival has been done.
        br = BofhdRequests(self.db, self.co)
        br.add_request(operator_id, br.now,
                       self.co.bofh_archive_user, ac.entity_id, None,
                       state_data=int(self.co.spread_uio_nis_user))
        self.logger.debug("Added archive_user request for %s" % guest)
        

    def get_owner(self, guestname):
        "Check that guestname is a guest account and that it has an owner."
        ac = Factory.get('Account')(self.db)    
        ac.find_by_name(guestname)
        owner = ac.get_trait(self.co.trait_guest_owner)
        if not owner:
            raise Errors.NotFoundError("Not a guest account.")
        if not owner['target_id']:
            raise GuestAccountException("Already available.")
        return int(owner['target_id'])

    def list_guest_users(self, owner_id=NotSet, include_comment=False):
        """List names of guest accounts owned by group with id=owner_id.
        If owner_id=None, return all available accounts.
        If no owner_id is specified, return all guest accounts.
        """
        ac = Factory.get('Account')(self.db)
        ret = []
        for row in ac.list_traits(self.co.trait_guest_owner,
                                  target_id=owner_id, return_name=True):
            # Must check if guest is available. 
            if owner_id is None and not self._guest_is_available(row['entity_id']):
                continue
            if include_comment:
                ret.append((row['name'], row['strval'] or ""))
            else:
                ret.append(row['name'])
        return ret

    def num_available_accounts(self):
        """Find num of available guest accounts."""
        return len(self.list_guest_users(owner_id=None))

    def find_new_guestusernames(self, num_new_guests, prefix="guest"):
        """Find next free guest user names for user_create_guest."""
        ac = Factory.get('Account')(self.db)
        ret = []
        num2guestname = {}
        # find all existing guests
        for uname in self.list_guest_users():
            if uname.startswith(prefix):
                continue
            num2guestname[int(uname[len(prefix):])] = uname
        # Find last guestuser num
        lastnum = 0
        guest_nums = num2guestname.keys()
        if guest_nums:
            guest_nums.sort()
            lastnum = guest_nums.pop()
        i = lastnum + 1  # uname number
        num_found = 0    # free guest account number
        tot_runs = 0     # To avoid infinite loop if error occurs
        while num_found < num_new_guests and i < 1000:
            uname = '%s%03d' % (prefix, i)
            i += 1
            if ac.validate_new_uname(self.co.account_namespace, uname):
                self.logger.debug("uname %s is legal and free" % uname)
                ret.append(uname)
                num_found += 1
            tot_runs += 1
        # If less than num guest account names was found, it's an error
        if num_found < num_new_guests:
            raise CerebrumError, ("Couldn't find more than %d guest account "
                                  "names in %sXXX namespace" %
                                  (num_found, prefix))
        return ret

    def _guest_is_available(self, e_id):
        "Check if guest is avaialable"
        ac = Factory.get('Account')(self.db)
        ac.find(e_id)
        # If guest has a quarantine it is not available
        if ac.get_entity_quarantine(self.co.quarantine_guest_release):
            return False
        return True

    def _alloc_guest(self, guest, end_date, comment, owner_type, owner_id,
                     operator_id):
        """Allocate a guest account.

        Make sure that the guest account requested actually exists and
        is available. If so, mark the account as taken by setting the
        owner trait.

        """
        ac = Factory.get('Account')(self.db)    
        self.logger.debug("Try to alloc %s" % guest)
        ac.clear()
        ac.find_by_name(guest)
        if ac.get_trait(self.co.trait_guest_owner)['target_id']:
            raise GuestAccountException("Guest user %s not available." % guest)
        if ac.get_entity_quarantine(self.co.quarantine_guest_release):
            # This should only happen if someone meddles manually
            self.logger.warn("Guest %s was unallocated, but had a quarantine" %
                             guest)
            ac.delete_entity_quarantine(self.co.quarantine_guest_release)
        # OK, add a quarantine which kicks in at end_date
        ac.add_entity_quarantine(self.co.quarantine_guest_release, operator_id,
                                 "Guest user request expired", start=end_date) 
        # Set owner trait
        self.logger.debug("Set owner_id in owner_trait for %s" % guest)
        if comment == '':
            comment = None
        ac.populate_trait(self.co.trait_guest_owner, target_id=owner_id,
                          strval=comment)
        ac.write_db()
        # Password
        pgpauth = self.co.Authentication("PGP-guest_acc")
        cryptstring = ac.get_account_authentication(pgpauth)
        passwd = ac.decrypt_password(pgpauth, cryptstring)
        return ac.entity_id, passwd


    def update_group_memberships(self, account_id):
        """Make sure that the account is a member of exactly the
        groups specified in cereconf.GUESTS_DEFAULT_FILEGROUP and
        cereconf.GUESTS_MEMBER_GROUPS.

        """
        user = PosixUser(self.db)
        user.find(account_id)
        gr = Factory.get("Group")(self.db)
        gr.find_by_name(cereconf.GUESTS_DEFAULT_FILEGROUP)
        user.gid_id = gr.entity_id
        user.write_db()
        req_groups = [gr.entity_id]
        # Add guest to the required groups
        for gr_name in cereconf.GUESTS_MEMBER_GROUPS:
            gr.clear()
            gr.find_by_name(gr_name)
            req_groups.append(gr.entity_id)
            member = gr.has_member(account_id)
            if member and member['operation'] != self.co.group_memberop_union:
                gr.remove_member(account_id, member['operation'])
                member = False
            if not member:
                gr.add_member(account_id, self.co.entity_account,
                              self.co.group_memberop_union)
        # Expel guest from any extra groups
        for row in gr.list_groups_with_entity(account_id):
            if row['group_id'] not in req_groups:
                gr.clear()
                gr.find(row['group_id'])
                gr.remove_member(account_id, row['operation'])

    def _find_guests(self, num_requested):
        ret = []
        num2guestname = {}
        # find all available guests
        for uname in self.list_guest_users(owner_id=None):
            try:
                prefix = uname.rstrip("0123456789")
                num = int(uname[len(prefix):])
                num2guestname[num] = uname
            except ValueError:
                self.logger.warn("%s is not a proper guestuser name." % uname)
                continue
        # Find best subset match 
        for start, end in self._find_subsets(num_requested,
                                             num2guestname.keys()):
            for i in range(start, end + 1):
                ret.append(num2guestname[i])
        return ret

    def _find_available_subsets(self, available_guests):
        """Return all available subsets sorted after increasing length
        as tuples on the form (len, start, stop).
        """
        tmp = {}       # found subsets placed here for later ordering
        ret = []       # list of subsets returned.

        available_guests.sort()
        first = available_guests[0]
        last  = available_guests[0]
        for i in available_guests[1:]:
            if i - last != 1:
                # Starting on new subset
                length = last - first + 1
                tmp[(first, last)] = length
                first = i
            last = i
        # Get last subset
        length = last - first + 1
        tmp[(first, last)] = length                   

        # Sort the subsets, the shortest first
        keys = _sort_by_value(tmp)
        for k in keys:
            ret.append((tmp[k], k[0], k[1]))
        return ret


    def _find_num_of_subsets(self, las, n):
        """ Returns the number of subsets necessary to allocate n spots. """
        i = -1
        x = las[i][0]   # length of longest available subset
        while x < n:
            i -= 1
            if len(las) < abs(i):  # Enough available subsets? 
                break
            x += las[i][0]
        return abs(i)

    def _find_best_subset_fit(self, las, num_requested, num_subsets):
        #  Try picking the shortest subset in las, and check if the
        #  other subset(s) is long enough to cover num_requested.
        #  If so:
        #      pick that
        #      same procedure with the next subsets
        #  else:
        #      pick next subset in las and check with that

        # get length, start- and end-position of shortest subset in las
        slen, start, end = las.pop(0) 
        if num_subsets == 1:              
            if num_requested <= slen:
                return start, start+num_requested-1

        l = slen
        i = 1
        use_shortest = False
        while num_subsets > i:
            l += las[-i][0]   
            if l >= num_requested:
                use_shortest = True
                break
            i += 1

        if use_shortest:
            return (start, end), self._find_best_subset_fit(las,
                                                            num_requested-slen,
                                                            num_subsets-1)
        # Try again, this time without the shortest interval
        return self._find_best_subset_fit(las, num_requested, num_subsets)


    def _find_subsets(self, num_requested, available_guests):
        """ Find subset(s) with total length num_requested.
        Return: ((start1, end1), (start2, end2), ...)
        """
        las = self._find_available_subsets(available_guests)
        num_subsets = self._find_num_of_subsets(las, num_requested)
        return _flatten(self._find_best_subset_fit(las, num_requested,
                                                   num_subsets))


def _sort_by_value(d):
    """ Returns the keys of dictionary d sorted by their values """
    items=d.items()
    backitems=[ [v[1],v[0]] for v in items]
    backitems.sort()
    return [ backitems[i][1] for i in range(0,len(backitems))]


def _flatten(tup):
    """ Flatten tuple tree to one tuple of (int, int) tuples. """
    res = []
    # If only one (a,b) tuple, just return
    if type(tup) is tuple and len(tup) == 2 and \
           type(tup[0]) is type(tup[1]) is int:
        res.append(tup)    
    else:
        # Nested, must go through elements
        for item in tup:
            if type(item) is tuple and len(item) == 2 and \
                   type(item[0]) is type(item[1]) is int:
                res.append(item)
            else:
                res.extend(_flatten(item))
    return res

# arch-tag: bd3d80d8-6272-11da-9a93-7a2e47a48ea3
