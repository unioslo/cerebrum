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

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
#from Cerebrum import Utils

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)    
prs = Factory.get('Person')(db)    
grp = Factory.get('Group')(db)    
logger = Factory.get_logger()


MIN_LENGTH = 5
VALID_GUEST_ACCOUNT_NAMES = ['guest%s' % str(i).zfill(3)
                             for i in range(1,cereconf.NR_GUEST_USERS+1)]

class GuestAccountException(Exception):
    """General exception for GuestAccount"""
    pass


def request_guest_users(nr, end_date, owner_type, owner):
    """Allocate nr number of guest users until manually released or
    until end_date. If the function fails because there are not enough
    guest users available raise GuestAccountException."""


    if nr > nr_available_accounts():
        raise GuestAccountException("Not enough guest accounts available. Use 'user guests_status' to find the nr of available guests.")
    
    return ['guest001', 'guest002'] # test

    ret = []
    failed = []
    for start, end in _find_subsets(nr):
        print "start %d, end %d" % (start, end)
        for i in range(start, end+1):
            guest = 'guest%s' % str(i).zfill(3)
            try:
                _alloc_guest(guest, end_date, owner_type, owner)
                ret.append(guest)            
            except (GuestAccountException, Errors.NotFoundError):
                failed.append(guest)
    # FIXME, vil jeg gjøre det slik?
    if failed:
        raise GuestAccountException("Failed to alloc %d guest accounts" % len(failed))
    return ret


# FIXME, karantene-bruken er utestet. Kan brekke...
def release_guest(guest, operator_id):
    """ Release a guest account

    Make sure that the guest account requested actually exists and
    mark it as released. If it already is released ignore this
    action and log a warning."""

    return  # Test
    ac.clear()
    ac.find_by_name(guest)
    # Set quarantine again
    today = DateTime.today()
    ac.add_entity_quarantine(co.quarantine_generell, operator_id,
                             "Released guest user.", today.date) 
    # Hva med owner, owner_type?


def get_guest(guestname):
    ac.clear()
    ac.find_by_name(guestname)
    return ac

# FIXME, lag ferdig list_guest_accounts
def list_guest_users(entity_type, owner):
    return "Not finished"
    ac.clear()
    return ac.list_guest_accounts(owner_id=owner.entity_id)
    

def nr_available_accounts():
    """ Find nr of available guest accounts. """

    return 400 # Test
    ret = 0
    for account_id, uname in ac.search(name="guest???"):
        ac.clear()
        if uname in VALID_GUEST_ACCOUNT_NAMES:
            ac.find(account_id)
            if ac.get_entity_quarantine(type=co.quarantine_generell):
                # Qurantine set, account is available. Er dette nok?
                ret += 1
    return ret


    
# Utility functions


# FIXME: passord,
def _alloc_guest(guest, end_date, owner_type, owner):
    """ Allocate a guest account.

    Make sure that the guest account requested actually exists and is
    available. If so set owner_type and owner. To mark the account as
    taken, disable quarantine until end_date"""

    ac.find_by_name(guest)
    if not ac.get_entity_quarantine(type=co.quarantine_generell):
        # This user should have been available...
        raise GuestAccountException("Couldn't alloc guest %s. Already taken." % guest)
    # OK, disable quarantine
    ac.disable_entity_quarantine(co.quarantine_generell, end_date)
    # Set end_date trait
    ac.populate_trait(self.const.trait_guest_end_date, date=end_date)

    ac.owner_type = owner_type
    ac.owner_id = owner.entity_id
    ac.write_db() # Riktig?
    # Passord...
    

def _find_available_subsets():
    """Return all available subsets with length > MIN_LENGTH.
       Subsets are sorted after increasing length.
    """
    first = None   # First element of a possible subset
    last = 0       # runs until last available spot of a subset
    tmp = {}       # found subsets placed here for later ordering
    ret = []       # list of subsets returned.
    i = 0
    while i < len(VALID_GUEST_ACCOUNT_NAMES):
        if _is_free(VALID_GUEST_ACCOUNT_NAMES[i]):
            print "Free"
            if first is None:
                first = i
            last = i
        else:
            if not first is None:
                length = last - first + 1
                if length >= MIN_LENGTH:
                    tmp[(first, last)] = length
            first = None
        i += 1
    # Get the last subset
    if not first is None:
        length = last - first + 1
        if length >= MIN_LENGTH:
            tmp[(first, last)] = length

    # Sort the subsets, the shortest first
    keys = _sort_by_value(tmp)
    for k in keys:
        ret.append((tmp[k], k[0], k[1]))
    return ret


def _find_nr_of_subsets(las, n):
    """ Returns the number of subsets necessary to allocate n spots. """
    i = -1
    x = las[i][0]   # length of longest available subset
    while x < n:
        i -= 1
        if len(las) < abs(i):  # Enough available subsets? 
            break
        x += las[i][0]
    if not x >= n:
        # Argh! Not enough available subsets of length > MIN_LENGTH. 
        return None
    return abs(i)


def _find_best_subset_fit(las, nr_of_slots_requested, nr_subsets):
    #  Try picking the shortest subset in las, and check if the
    #  other subset(s) is long enough to cover nr_of_slots_requested.
    #  If so:
    #      pick that
    #      same procedure with the next subsets
    #  else:
    #      pick next subset in las and check with that

    # NB! Algoritmen er kanskje litt "utrygg". Den vil kun virke om
    # nr_of_slots_requested <= antall ledige slots i las (List of
    # Available subsets) og nr_subsets >= 1. Hvis dette ikke er testet
    # før denne funskjonen kalles kan det fort gå til helvete. 

    # get length, start- and end-position of shortest subset in las
    slen, start, end = las.pop(0) 
    
    if nr_subsets == 1:              
        if nr_of_slots_requested <= slen:
            return start, start+nr_of_slots_requested-1
        # If this test fails the loop will be skipped and the else
        # branch below  will run.

    l = slen
    i = 1
    use_shortest = False
    while nr_subsets > i:
        l += las[-i][0]   
        if l >= nr_of_slots_requested:
            use_shortest = True
            break
        i += 1

    if use_shortest:
        return (start, end), _find_best_subset_fit(las, nr_of_slots_requested-slen,
                                                  nr_subsets-1)
    else:
        return _find_best_subset_fit(las, nr_of_slots_requested, nr_subsets)


def _find_subsets(nr_of_slots_requested):
    """ Find subset(s) with total length nr_of_slots_requested.
    Return: ((start1, end1), (start2, end2), ...)
    """
    las = _find_available_subsets()
    nr_subsets = _find_nr_of_subsets(las, nr_of_slots_requested)
    # If nr_subsets is None, then the total number of free slots in
    # las isn't enough. The only solution is to use all the available
    # slots until nr_of_slots_requested slots are allocated.    
    if not nr_subsets:
        MIN_LENGTH = 1
        return _find_subsets(nr_of_slots_requested)

    return _flatten(_find_best_subset_fit(las, nr_of_slots_requested, nr_subsets))


# FIXME, burde ha en cache eller noe...
def _is_free(uname):
    ac.clear()
    if uname in VALID_GUEST_ACCOUNT_NAMES:
        try:
            ac.find_by_name(uname)
            if ac.get_entity_quarantine(type=co.quarantine_generell):
                # Qurantine set, account is available. Er dette nok?
                return True
        except:
            return False
    return False
 
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
