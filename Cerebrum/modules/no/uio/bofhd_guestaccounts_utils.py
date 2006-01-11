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
import os
import time
from mx import DateTime

import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory

VALID_GUEST_ACCOUNT_NAMES = ['guest%s' % str(i).zfill(3)
                             for i in range(1,cereconf.NR_GUEST_USERS+1)]

class SimpleLogger(object):
    # Unfortunately we cannot user Factory.get_logger due to the
    # singleton behaviour of cerelog.get_logger().  Once this is
    # fixed, this class can be removed.
    def __init__(self, fname):
        self.stream = open(
            os.path.join(cereconf.AUTOADMIN_LOG_DIR, fname), 'a+')
        
    def show_msg(self, lvl, msg, exc_info=None):
        self.stream.write("%s %s [%i] %s\n" % (
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            lvl, os.getpid(), msg))
        self.stream.flush()

    def debug2(self, msg, **kwargs):
        self.show_msg("DEBUG2", msg, **kwargs)
    
    def debug(self, msg, **kwargs):
        self.show_msg("DEBUG", msg, **kwargs)

    def info(self, msg, **kwargs):
        self.show_msg("INFO", msg, **kwargs)

    def error(self, msg, **kwargs):
        self.show_msg("ERROR", msg, **kwargs)

    def fatal(self, msg, **kwargs):
        self.show_msg("FATAL", msg, **kwargs)

    def critical(self, msg, **kwargs):
        self.show_msg("CRITICAL", msg, **kwargs)


class GuestAccountException(Exception):
    """General exception for GuestAccount"""
    pass


class BofhdUtils(object):
    def __init__(self, server):
        self.server = server
        self.db = server.db
        self.co = Factory.get('Constants')(self.db)
        self.ac = Factory.get('Account')(self.db)    
        #self.prs = Factory.get('Person')(self.db)    
        #self.grp = Factory.get('Group')(self.db)    
        self.logger = SimpleLogger('pq_bofhd.log')


    def request_guest_users(self, nr, end_date, owner_type, owner_id):
        """Allocate nr number of guest users until manually released or
        until end_date. If the function fails because there are not enough
        guest users available raise GuestAccountException."""

        if nr > self.nr_available_accounts():
            raise GuestAccountException("Not enough available guest users.\nUse 'user guests_status' to find the number of available guests.")

        ret = []
        failed = []
        for start, end in self._find_subsets(nr):
            for i in range(start, end+1):
                guest = VALID_GUEST_ACCOUNT_NAMES[i]
                try:
                    self._alloc_guest(guest, end_date, owner_type, owner_id)
                    ret.append(guest)            
                except (GuestAccountException, Errors.NotFoundError):
                    failed.append(guest)

        # If for some reason there is a partial failure, should we try to
        # fix it? If LITA wants to require 50 guests, but _alloc_guest
        # only succeeds in 49 of the cases it makes little sense to give
        # up. Discuss and fix.
        if failed:
            raise GuestAccountException("Failed to alloc %d guest users" %
                                        len(failed))
        return ret


    def release_guest(self, guest, operator_id):
        """ Release a guest account

        Make sure that the guest account requested actually exists and
        mark it as released. If it already is released ignore this
        action and log a warning."""

        if self._is_free(guest):
            raise GuestAccountException("Guest user %s is already available." %
                                        guest)

        self.ac.clear()
        self.ac.find_by_name(guest)
        # Set normal quarantine again to mark that the account is free
        # Only way to do this is to delete disabled quarantine and set new
        # quarantine. It would be useful with another way to do this.    
        today = DateTime.today()
        self.ac.delete_entity_quarantine(self.co.quarantine_generell) 
        self.ac.add_entity_quarantine(self.co.quarantine_generell, operator_id,
                                      "Released guest user.", today.date) 
        # Delete trait to mark that account has no temporay owner
        old = self.ac.get_trait(self.co.trait_guest_owner)
        if old:
            self.ac.delete_trait(self.co.trait_guest_owner)
        else:
            self.logger.warn("Tried to delete owner trait for %s, but guest "\
                             "account has no owner trait. Suspicious!" % guest)


    def get_guest(self, guestname):
        self.ac.clear()
        self.ac.find_by_name(guestname)
        return self.ac


    # TBD, efficiency improvements can be done...
    def list_guest_users(self, entity_type, owner_id):
        ret = []
        self.ac.clear()
        for row in self.ac.list_traits(self.co.trait_guest_owner):
            if int(owner_id) == int(row[3]):
                self.ac.clear()
                self.ac.find(row[0])
                ret.append(self.ac.account_name)

        return ret

    # TBD, efficiency improvements can be done...
    def nr_available_accounts(self):
        """ Find nr of available guest accounts. """

        ret = 0
        for account_id, uname in self.ac.search(name="guest???"):
            self.ac.clear()
            if uname in VALID_GUEST_ACCOUNT_NAMES:
                self.ac.find(account_id)
                if self.ac.get_entity_quarantine(type=self.co.quarantine_generell,
                                                 only_active=True):
                    # Qurantine set, account is available. 
                    ret += 1
        return ret


    # TBD, efficiency improvements can be done...
    def _is_free(self, uname):
        self.ac.clear()
        if uname in VALID_GUEST_ACCOUNT_NAMES:
            try:
                self.ac.find_by_name(uname)
                if self.ac.get_entity_quarantine(type=self.co.quarantine_generell,
                                                 only_active=True):
                    # Qurantine is set, account is available. 
                    return True
            except:
                return False
        return False


# FIXME: passord,
    def _alloc_guest(self, guest, end_date, owner_type, owner_id):
        """ Allocate a guest account.

        Make sure that the guest account requested actually exists and is
        available. If so set owner trait and mark the account as taken by
        disabling quarantine until end_date"""

        self.logger.debug("Try to alloc %s" % guest)
        self.ac.clear()
        self.ac.find_by_name(guest)
        if not self.ac.get_entity_quarantine(type=self.co.quarantine_generell,
                                             only_active=True):
            # This user should have been available...
            raise GuestAccountException("Guest user %s not available. " % guest)
        # OK, disable quarantine
        self.logger.debug("Disable quarantine for %s" % guest)
        self.ac.disable_entity_quarantine(int(self.co.quarantine_generell),
                                          end_date)
        # Set end_date trait
        self.logger.debug("populate trait for %s" % guest)
        self.ac.populate_trait(self.co.trait_guest_owner, target_id=owner_id)
        self.ac.write_db()
        # Passord...


    def _find_available_subsets(self):
        """Return all available subsets sorted after increasing length.
        """
        first = None   # First element of a possible subset
        last = 0       # runs until last available spot of a subset
        tmp = {}       # found subsets placed here for later ordering
        ret = []       # list of subsets returned.
        i = 0
        while i < len(VALID_GUEST_ACCOUNT_NAMES):
            if self._is_free(VALID_GUEST_ACCOUNT_NAMES[i]):
                self.logger.debug("%s is free" % VALID_GUEST_ACCOUNT_NAMES[i])
                if first is None:
                    first = i
                last = i
            else:
                self.logger.debug("%s is taken." % VALID_GUEST_ACCOUNT_NAMES[i])
                if not first is None:
                    length = last - first + 1
                    tmp[(first, last)] = length
                first = None
            i += 1
        # Get the last subset
        if not first is None:
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


    def _find_subsets(self, nr_requested):
        """ Find subset(s) with total length nr_requested.
        Return: ((start1, end1), (start2, end2), ...)
        """
        las = self._find_available_subsets()
        nr_subsets = self._find_nr_of_subsets(las, nr_requested)

        return _flatten(self._find_best_subset_fit(las, nr_requested,
                                                   nr_subsets))

 
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

