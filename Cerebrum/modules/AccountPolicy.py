# -*- coding: utf-8 -*-
#
# Copyright 2019 University of Oslo, Norway
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
from __future__ import unicode_literals
import datetime

import cereconf

from Cerebrum.Errors import InvalidAccountCreationArgument
from Cerebrum.Utils import Factory
from Cerebrum.modules.disk_quota import DiskQuota
from Cerebrum.utils.email import is_email


def _set_account_type(account, person, affiliation, ou_id):
    person_affiliations = person.list_affiliations(
        person_id=person.entity_id,
        affiliation=affiliation,
        ou_id=ou_id
    )
    try:
        person_aff = person_affiliations[0]
    except IndexError:
        raise InvalidAccountCreationArgument(
            'Account can not get affiliation {}, which the owner {} does '
            'not have'.format((affiliation, ou_id),
                              person.entity_id)
        )
    account.set_account_type(person_aff['ou_id'], person_aff['affiliation'])


def _set_account_types(account, person, affiliations):
    for affiliation in affiliations:
        _set_account_type(account,
                          person,
                          affiliation['affiliation'],
                          affiliation['ou_id'])


class AccountPolicy(object):
    def __init__(self, db):
        self.db = db
        self.const = Factory.get('Constants')(db)
        self.account = Factory.get('Account')(db)
        self.posix_user = Factory.get('PosixUser')(db)
        self.disk_quota = DiskQuota(db)

    def create_basic_account(self, creator_id, owner, uname, np_type=None):
        self.account.clear()
        if not self.account.is_valid_new_uname:
            raise InvalidAccountCreationArgument('Username already taken: %r'
                                                 % uname)
        self.account.populate(uname,
                              owner.entity_type,
                              owner.entity_id,
                              np_type,
                              creator_id,
                              None)
        self.account.write_db()
        return Factory.get('Account')(self.db).find(self.account.entity_id)

    def create_group_account(self, creator_id, uname, owner_group,
                             contact_address, account_type):
        account = self.create_basic_account(creator_id,
                                            owner_group,
                                            uname,
                                            account_type)
        if not is_email(contact_address):
            raise InvalidAccountCreationArgument('Invalid email address: %s',
                                                 contact_address)

        # Unpersonal accounts shouldn't normally have a mail inbox, but they
        # get a forward target for the account, to be sent to those responsible
        # for the account, preferrably a sysadm mail list.
        if hasattr(account, 'add_contact_info'):
            account.add_contact_info(self.const.system_manual,
                                     self.const.contact_email,
                                     contact_address)

        if cereconf.BOFHD_CREATE_UNPERSONAL_QUARANTINE:
            qconst = self.const.Quarantine(
                cereconf.BOFHD_CREATE_UNPERSONAL_QUARANTINE
            )
            account.add_entity_quarantine(qconst, creator_id,
                                          "Not granted for global password "
                                          "auth (ask IT-sikkerhet)",
                                          datetime.date.today().isoformat())
        return account

    def _make_posix_user(self, gid, gecos, shell, expire_date):
        self.posix_user.clear()
        uid = self.posix_user.get_free_uid()
        self.posix_user.populate(
            uid,
            gid,
            gecos,
            shell,
            parent=self.account,
            expire_date=expire_date
        )
        self.posix_user.write_db()

    def _set_user_disk(self, account, disk_id, home_spread, home=None,
                       disk_quota=None):
        if home:
            homedir_id = account.set_homedir(
                disk_id=disk_id,
                status=self.const.home_status_not_created,
                home=home
            )
        else:
            homedir_id = account.set_homedir(
                disk_id=disk_id,
                status=self.const.home_status_not_created
            )
        account.set_home(home_spread, homedir_id)
        if disk_quota:
            self.disk_quota.set_quota(homedir_id, quota=int(disk_quota))

    def create_personal_account(self, person, affiliations, disks, expire_date,
                                creator_id, uname=None, traits=(), spreads=(),
                                make_posix_user=True,
                                gid=None, shell=None):
        """Create a personal account for the given person

        :type person: populated Cerebrum.Utils._dynamic_Person
        :type affiliations: dicts containing keys 'affiliation' and 'ou_id'
        :param affiliations: affiliations to set on the account
        :type disks: Iterables containing values 'disk_id', 'home_spread',
            'home' and 'disk_quota'
        :param disks: disks to give the user
        :param uname: the desired user name
        :param traits: traits to add to the newly created account
        :param spreads: spreads to add to the newly created account
        :param make_posix_user: should the account be a posix user?
        :return: Account
        """
        if make_posix_user:
            account = self.posix_user
        else:
            account = self.account

        if uname is None:
            uname = account.suggest_unames(person)[0]

        self.account.clear()
        self.account.populate(uname,
                              self.const.entity_person,
                              person.entity_id,
                              None,
                              creator_id,
                              expire_date)
        self.account.write_db()
        for trait in traits:
            self.account.populate_trait(code=trait, date=datetime.date.today())
        self.account.write_db()
        if make_posix_user:
            self._make_posix_user(gid, None, shell, expire_date)
        for spread in spreads:
            account.add_spread(spread)
        for disk_id, home_spread, home, disk_quota in disks:
            self._set_user_disk(account,
                                disk_id,
                                home_spread,
                                home=home,
                                disk_quota=disk_quota)
        _set_account_types(account, person, affiliations)
        # Returning a new account object to avoid accidentally modifying it
        # if creating another account.
        return Factory.get('Account')(self.db).find(account.entity_id)
