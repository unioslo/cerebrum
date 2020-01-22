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
from Cerebrum.modules.ou_disk_mapping import utils
from Cerebrum.modules.ou_disk_mapping.dbal import OUDiskMapping


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
        self.disk_mapping = OUDiskMapping(db)

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
        new_account = Factory.get('Account')(self.db)
        new_account.find(self.account.entity_id)
        return new_account

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

    def _get_ou_disk(self, person):
        # Get highest precedent affiliation
        _, ou_id, aff, _, status, _, _, _, _ = person.list_affiliations(
            person.entity_id)[0]
        # Find the right disk id for this person
        if aff:
            aff = self.const.PersonAffiliation(aff)
        if status:
            status = self.const.PersonAffStatus(status)
        disk_id = utils.get_disk(
            self.db,
            self.disk_mapping,
            ou_id,
            aff,
            status,
            self.const.OUPerspective(cereconf.DEFAULT_OU_PERSPECTIVE))
        home_spread = int(self.const.Spread(cereconf.DEFAULT_HOME_SPREAD))
        return disk_id, home_spread

    def update_account(self, person, account_id, *args, **kwargs):
        self.account.clear()
        self.account.find(account_id)
        return self._update_account(person, *args, **kwargs)

    def _update_account(self, person, affiliations, disks,
                        expire_date, traits=(), spreads=(),
                        make_posix_user=True, gid=None, shell=None,
                        ou_disk=False):
        """Update an account

        Adds traits, spreads and disks to an account, and also promotes posix.
        Note self.account must already populated.
        """
        for trait in traits:
            self.account.populate_trait(code=trait, date=datetime.date.today())
        self.account.write_db()
        if make_posix_user:
            self._make_posix_user(gid, None, shell, expire_date)
        user = self._get_user_obj(make_posix_user)
        for spread in spreads:
            user.add_spread(spread)
        if ou_disk and not disks:
            disk_id, home_spread = self._get_ou_disk(person)
            disks = ({'disk_id': disk_id, 'home_spread': home_spread},)
        for disk in disks:
            self._set_user_disk(user,
                                disk['disk_id'],
                                disk['home_spread'],
                                home=disk.get('home', None),
                                disk_quota=disk.get('disk_quota', None))
        _set_account_types(user, person, affiliations)
        user.write_db()
        return user

    def _get_user_obj(self, posix):
        if posix:
            return self.posix_user
        else:
            return self.account

    def create_personal_account(self, person, affiliations, disks, expire_date,
                                creator_id, uname=None, traits=(), spreads=(),
                                make_posix_user=True, gid=None, shell=None,
                                ou_disk=False):
        """Create a personal account for the given person

        :type person: populated Cerebrum.Utils._dynamic_Person
        :type affiliations: dicts containing keys 'affiliation' and 'ou_id'
        :param affiliations: affiliations to set on the account
        :type disks: Iterable
        :param disks: disks to give the user. Each disk is a dict with
            the required keys 'disk_id', 'home_spread' and optional keys
            'home', 'disk_quota'.
        :param uname: the desired user name
        :param traits: traits to add to the newly created account
        :param spreads: spreads to add to the newly created account
        :param make_posix_user: should the account be a posix user?
        :type ou_disk: bool
        :param ou_disk: should a disk be selected using the OUDiskMapping
            module if disks parameter is empty?
        :return: Account or PosixUser
        """
        user = self._get_user_obj(make_posix_user)
        if uname is None:
            user_names = user.suggest_unames(person)
            try:
                uname = user_names[0]
            except IndexError:
                raise InvalidAccountCreationArgument(
                    'Could not generate user name for person %s',
                    person.entity_id
                )

        self.account.clear()
        self.account.populate(uname,
                              self.const.entity_person,
                              person.entity_id,
                              None,
                              creator_id,
                              expire_date)
        self.account.write_db()
        user = self._update_account(person, affiliations,
                                    disks, expire_date,
                                    traits=traits, spreads=spreads,
                                    make_posix_user=make_posix_user,
                                    gid=gid,
                                    shell=shell, ou_disk=ou_disk)
        # Returning a new account object to avoid accidentally modifying the
        # current one when creating another account.
        if make_posix_user:
            new_account = Factory.get('PosixUser')(self.db)
        else:
            new_account = Factory.get('Account')(self.db)
        new_account.find(user.entity_id)
        return new_account
