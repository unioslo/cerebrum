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
from Cerebrum.Utils import Factory


class GuestAccountException(Exception):
    """General exception for GuestAccount"""
    pass


class BofhdUtils(object):
    def __init__(self, server):
        self.server = server
        self.db = server.db
        self.co = Factory.get('Constants')(self.db)
        self.logger = server.logger


    def request_guest_users(self, nr, end_date, owner_type, owner_id):
        """Allocate nr number of guest users until manually released or
        until end_date. If the function fails because there are not enough
        guest users available raise GuestAccountException."""

        if nr > self.nr_available_accounts():
            raise GuestAccountException("Not enough available guest users.\nUse 'user guests_status' to find the number of available guests.")

        ret = []
        for guest in self._find_guests(nr):
            try:
                self._alloc_guest(guest, end_date, owner_type, owner_id)
                ret.append(guest)            
            except (GuestAccountException, Errors.NotFoundError):
                # If one alloc fails the request fails. 
                raise GuestAccountException("Could not allocate guests")
        return ret


    def release_guest(self, guest, operator_id):
        """ Release a guest account

        Make sure that the guest account requested actually exists and
        mark it as released. If it already is released ignore this
        action and log a warning."""

        if self._is_free(guest):
            raise GuestAccountException("%s is already available." % guest)

        ac = Factory.get('Account')(self.db)    
        ac.clear()
        ac.find_by_name(guest)
        # Set normal quarantine again to mark that the account is free
        # Only way to do this is to delete disabled quarantine and set new
        # quarantine. It would be useful with another way to do this.    
        today = DateTime.today()
        ac.delete_entity_quarantine(self.co.quarantine_generell) 
        ac.add_entity_quarantine(self.co.quarantine_generell, operator_id,
                                      "Released guest user.", today.date) 
        self.logger.debug("Quarantine reset for %s." % guest)
        ac.populate_trait(self.co.trait_guest_owner, target_id=None)
        self.logger.debug("Removed owner_id in owner_trait for %s" % guest)
        ac.write_db()


    def get_owner(self, guestname):
        "Check that guestname is a guest account and that it has an owner."
        ac = Factory.get('Account')(self.db)    
        ac.clear()
        ac.find_by_name(guestname)
        owner = ac.get_trait(self.co.trait_guest_owner)
        if not owner:
            raise Errors.NotFoundError("Not a guest account.")
        if not owner['target_id']:
            raise GuestAccountException("Already available.")
        return int(owner['target_id'])


    def list_guest_users(self, owner_id):
        "List guest users owned by group with id=owner_id."
        ac = Factory.get('Account')(self.db)
        ret = []
        ac.clear()
        for row in ac.list_traits(self.co.trait_guest_owner):
            if row['target_id'] and int(owner_id) == int(row['target_id']):
                ac.clear()
                ac.find(row['entity_id'])
                ret.append(ac.account_name)
        return ret


    def nr_available_accounts(self):
        """ Find nr of available guest accounts. """
        return len(self._available_guests())


    def _available_guests(self):
        """ Return the available guest accounts names """
        ac = Factory.get('Account')(self.db)    
        ret = []

        for row in ac.list_traits(self.co.trait_guest_owner):
            ac.clear()
            ac.find(row['entity_id'])
            if ac.get_entity_quarantine(type=self.co.quarantine_generell,
                                        only_active=True):
                ret.append(ac.account_name)            
        return ret


    def _is_free(self, uname):
        ac = Factory.get('Account')(self.db)    
        ac.clear()
        ac.find_by_name(uname)            
        if ac.get_entity_quarantine(type=self.co.quarantine_generell,
                                    only_active=True):
            return True
        return False


    def _alloc_guest(self, guest, end_date, owner_type, owner_id):
        """ Allocate a guest account.

        Make sure that the guest account requested actually exists and is
        available. If so set owner trait and mark the account as taken by
        disabling quarantine until end_date"""

        ac = Factory.get('Account')(self.db)    
        self.logger.debug("Try to alloc %s" % guest)
        ac.clear()
        ac.find_by_name(guest)
        if not ac.get_entity_quarantine(type=self.co.quarantine_generell,
                                        only_active=True):
            raise GuestAccountException("Guest user %s not available." % guest)
        # OK, disable quarantine until end_date
        self.logger.debug("Disable quarantine for %s" % guest)
        ac.disable_entity_quarantine(int(self.co.quarantine_generell),
                                     end_date)
        # Set owner trait
        self.logger.debug("Set owner_id in owner_trait for %s" % guest)
        ac.populate_trait(self.co.trait_guest_owner, target_id=owner_id)
        ac.write_db()
        # Passord...


    def _find_guests(self, nr_requested):
        ret = []
        nr2guestname = {}
        # find all available guests
        for uname in self._available_guests():
            prefix, nr = _mysplit(uname)
            nr2guestname[nr] = uname
        # Find best subset match 
        for start, end in self._find_subsets(nr_requested, nr2guestname.keys()):
            for i in range(start, end+1):
                ret.append(nr2guestname[i])
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


    def _find_nr_of_subsets(self, las, n):
        """ Returns the number of subsets necessary to allocate n spots. """
        i = -1
        x = las[i][0]   # length of longest available subset
        while x < n:
            i -= 1
            if len(las) < abs(i):  # Enough available subsets? 
                break
            x += las[i][0]

        return abs(i)


    def _find_best_subset_fit(self, las, nr_requested, nr_subsets):
        #  Try picking the shortest subset in las, and check if the
        #  other subset(s) is long enough to cover nr_requested.
        #  If so:
        #      pick that
        #      same procedure with the next subsets
        #  else:
        #      pick next subset in las and check with that

        # get length, start- and end-position of shortest subset in las
        slen, start, end = las.pop(0) 
        if nr_subsets == 1:              
            if nr_requested <= slen:
                return start, start+nr_requested-1

        l = slen
        i = 1
        use_shortest = False
        while nr_subsets > i:
            l += las[-i][0]   
            if l >= nr_requested:
                use_shortest = True
                break
            i += 1

        if use_shortest:
            return (start, end), self._find_best_subset_fit(las,
                                                            nr_requested-slen,
                                                            nr_subsets-1)
        # Try again, this time without the shortest interval
        return self._find_best_subset_fit(las, nr_requested, nr_subsets)


    def _find_subsets(self, nr_requested, available_guests):
        """ Find subset(s) with total length nr_requested.
        Return: ((start1, end1), (start2, end2), ...)
        """
        las = self._find_available_subsets(available_guests)
        nr_subsets = self._find_nr_of_subsets(las, nr_requested)
        return _flatten(self._find_best_subset_fit(las, nr_requested,
                                                   nr_subsets))


def _mysplit(arg):
    """Split string arg into prefix and number if arg ends with a
    string representation of decimal numbers.
    """
    if arg and isinstance(arg, str) and len(arg) >= 2:
        i = len(arg)
        try:        
            while i > 0:
                tmp = int(arg[i-1])
                i -= 1
        except ValueError:
            if i < len(arg):
                return arg[:i], int(arg[i:])
    return None, None


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

