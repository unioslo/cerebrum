# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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

from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr
from SpineLib.Builder import Method
from SpineLib.SpineExceptions import NotFoundError

from Account import Account
from Disk import Disk
from Types import Spread, HomeStatus

from SpineLib import Registry
registry = Registry.get_registry()

homedir_table = 'homedir'
class HomeDirectory(DatabaseClass):
    """HomeDirecory describes where to find an accounts homedir.

    An account can have a homedir for each spread, but can only have one
    homedir for a given home/disk. All AccountHomes who points to the
    homedir must be removed before the homedir can be removed, which
    will automaticly remove the homedir.
    
    The homedirectory can either be set as a string in 'home', or through
    a disk+host with 'disk'.

    'home' and 'disk' is mutualy exclusive, and therefor not writeable,
    but should be updated with the method set_homedir() on account.
    """
    primary = (
        DatabaseAttr('id', homedir_table, int),
    )

    slots = (
        DatabaseAttr('account', homedir_table, Account),
        DatabaseAttr('home', homedir_table, str),
        DatabaseAttr('disk', homedir_table, Disk),
        DatabaseAttr('status', homedir_table, HomeStatus, write=True)
    )

    method_slots = (
        Method('get_path', str),
    )

    db_attr_aliases = {
        homedir_table:{
            'id':'homedir_id',
            'account':'account_id',
            'disk':'disk_id',
        }
    }

    def get_path(self):
        """Returns the path from either disk or home."""
        path = None
        if self.get_home():
            path = self.get_home()
        elif self.get_disk():
            #FIXME: is this good enough?
            path = self.get_disk().get_host().get_name()
            path += ':'+self.get_disk().get_path()
        return path

registry.register_class(HomeDirectory)

home_table = 'account_home'
class AccountHome(DatabaseClass):
    """AccountHome links homedir with an account and a spread.

    When all AccountHomes which points to a HomeDirectory is deleted, the
    HomeDirectory will also be removed.
    """
    primary = (
        DatabaseAttr('account', home_table, Account),
        DatabaseAttr('spread', home_table, Spread)
    )
    slots = (
        DatabaseAttr('homedir', home_table, HomeDirectory),
    )

    method_slots = (
        Method('delete', None, write=True),
    )

    db_attr_aliases = {
        home_table:{
            'account':'account_id',
            'homedir':'homedir_id'
        }
    }

    def delete(self):
        account = self.get_account()
        acc_obj = account._get_cerebrum_obj()
        acc_obj.clear_home(self.get_spread().get_id())

registry.register_class(AccountHome)

def _get_homedir(db, account, spread):
    """Returns the homedir if it exists."""
    searcher = registry.AccountHomeSearcher(db)
    searcher.set_account(account)
    searcher.set_spread(spread)
    result = searcher.search()
    return result and result[0].get_homedir() or None

def set_homedir(self, spread, home="", disk=None):
    """Set the home or disk for the homedir on the given spread.

    Since we dont support default arguments over corba the clients needs to
    supply the default arguments themselfs.

    If the account already have a homedir for the spread, it will be updated.
    The status will be set to default value of 'not_created'.
    Clients which syncs the homedir should update the status.
    """
    db = self.get_database()
    obj = self._get_cerebrum_obj()
    homedir = _get_homedir(db, self, spread)
    
    # vargs contains the arguments sent to set_homedir in cerebrum-core
    vargs = {}
    if homedir:
        vargs['current_id'] = homedir.get_id()
    if home:
        vargs['home'] = home
    if disk:
        vargs['disk_id'] = disk.get_id()
    vargs['status'] = registry.HomeStatus(db, name='not_created').get_id()

    homedir_id = obj.set_homedir(**vargs)

    if not homedir:
        obj.set_home(spread.get_id(), homedir_id)
    else:
        homedir.reset(write_only=False) # home and disk is no longer correct

Account.register_method(Method('set_homedir', None, args=[('spread', Spread),
                        ('home', str), ('disk', Disk)], write=True), set_homedir)

def remove_homedir(self, spread):
    """Removes the homedir for the given spread."""
    home = AccountHome(self.get_database(), self, spread)
    home.delete()

Account.register_method(Method('remove_homedir', None,
    args=[('spread', Spread)], exceptions=[NotFoundError]), remove_homedir)

def get_homedir(self, spread):
    """Returns the homedir for the given spread."""
    home = AccountHome(self.get_database(), self, spread)
    return home.get_homedir()

Account.register_method(Method('get_homedir', HomeDirectory,
    args=[('spread', Spread)], exceptions=[NotFoundError]), get_homedir)

def get_homes(self):
    """Returns all homes this account has.
    
    This account-method behaves diffrently than the other methods
    which is related to homedir in the way it returns AccountHome-objects
    instead of HomeDirectory-objects. This is done to give the client
    information about which spread the HomeDirectory is for.
    """
    searcher = registry.AccountHomeSearcher(self.get_database())
    searcher.set_account(self)
    return searcher.search()

Account.register_method(Method('get_homes', [AccountHome]), get_homes)

# arch-tag: f1f89d6e-8174-4d53-82ac-c21885a8b574
