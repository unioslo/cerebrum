#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2012 University of Oslo, Norway
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

"""Commands for the bofh daemon regarding the guest user functionality.

"""

from mx import DateTime

import cerebrum_path
import cereconf
import guestconfig

from Cerebrum import Errors
from Cerebrum.Utils import Factory, SMSSender
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.auth import BofhdAuth

from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.cmd_param import Parameter, Command, AccountName, \
        Integer, GroupName, PersonName, FormatSuggestion

def format_day(field):
    fmt = "yyyy-MM-dd"                  # 10 characters wide
    return ":".join((field, "date", fmt))

class Mobile(Parameter):
    _type = 'mobilePhone'
    _help_ref = 'mobile_number'

class BofhdExtension(BofhdCommandBase):
    all_commands = {}

    def __init__(self, server):
        super(BofhdExtension, self).__init__(server)
        # TODO: need to be able to change BofhdAuth dynamically for each
        # instance
        self.ba = BofhdAuth(self.db)

    def get_help_strings(self):
        group_help = {
            'guest': "Commands for handling guest users",
            }

        # The texts in command_help are automatically line-wrapped, and should
        # not contain \n
        command_help = {
            'guest': {
            'guest_create': 'Create a new guest user',
            'guest_list': 'List out all guest users for a given owner',
            },
            }
        
        arg_help = {
            'guest_days':
            ['days', 'Enter number of days',
             'Enter the number of days the guest user should be active'],
            'guest_fname':
            ['given_name', "Enter guest's given name",
             "Enter the guest's first and middle name"],
            'guest_lname':
            ['family_name', "Enter guest's family name",
             "Enter the guest's (last) family name"],
            'guest_responsible':
            ['responsible', "Enter the responsible user",
             "Enter the user that will be set as the responsible for the "
             "guest"],
            'group_name':
            ['group', 'Enter group name',
             "Enter the group the guest should belong to"],
            'mobile_number':
            ['mobile', 'Enter mobile number',
             "Enter the guest's mobile number, where the username and password "
             "will be sent"],
            }
        return (group_help, command_help, arg_help)

    def _get_owner_group(self):
        """Get the group that should stand as the owner of the guest accounts.
        Note that this is different from the 'responsible' account for a guest,
        which is stored in a trait.

        The owner group will be created if it doesn't exist.

        """
        gr = self.Group_class(self.db)
        try:
            gr.find_by_name(guestconfig.GUEST_OWNER_GROUP)
            return gr
        except Errors.NotFoundError:
            # Group does not exist, must create it
            pass
        self.logger.info('Creating guest owner group %s' %
                         guestconfig.GUEST_OWNER_GROUP)
        ac = self.Account_class(self.db)
        ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        gr.populate(creator_id = ac.entity_id,
                    visibility = self.const.group_visibility_all,
                    name = guestconfig.GUEST_OWNER_GROUP,
                    description = "The owner of all the guest accounts")
        gr.write_db()
        return gr

    def _get_guest_group(self, groupname, operator_id):
        """Get the given guest group. Gets created it if it doesn't exist.
        """
        if not guestconfig.GUEST_TYPES.has_key(groupname):
            raise CerebrumError('Given group not defined as a guest group')
        try:
            return self._get_group(groupname)
        except CerebrumError:
            # Mostlikely not created yet
            pass
        self.logger.info('Creating guest group %s' % groupname)
        group = self.Group_class(self.db)
        group.populate(creator_id = operator_id, name = groupname,
                visibility = self.const.group_visibility_all,
                description = "For guest accounts")
        group.write_db()
        return group

    def _get_guests(self, responsible_id):
        """Get a list of guest accounts that belongs to a given account.

        @type responsible: int
        @param responsible: The responsible's entity_id

        @rtype: list
        @return: A list of db rows from ent.list_trait. The interesting keys
                 are entity_id, target_id and strval.

        """
        return self.Account_class(self.db).list_traits(
                                code = self.const.trait_guest_owner,
                                target_id = responsible_id)

    # guest create
    all_commands['guest_create'] = Command(
            ("guest", "create"),
            Integer(help_ref='guest_days'),
            PersonName(help_ref='guest_fname'),
            PersonName(help_ref='guest_lname'),
            GroupName(),
            Mobile(optional=True),
            AccountName(help_ref='guest_responsible', optional=True),
            perm_filter='can_create_personal_guest')
    def guest_create(self, operator, days, fname, lname, groupname, mobile=None,
                     responsible=None):
        """Create and set up a new guest account."""
        self.ba.can_create_personal_guest(operator.get_entity_id())

        # input validation
        try:
            days = int(days)
        except ValueError, e:
            raise CerebrumError('The number of days must be an integer')
        if not (0 < days <= guestconfig.GUEST_MAX_DAYS):
            raise CerebrumError('Invalid number of days, must be in the '
                                'range 1-%d' % guestconfig.GUEST_MAX_DAYS)
        if not fname or len(fname.strip()) < 2:
            raise CerebrumError('First name must be at least 2 characters long')
        if not lname or len(lname.strip()) < 1:
            raise CerebrumError('Last name must be at least one character long')
        # TODO: add checks for if name is longer than 512 characters (as is max
        # for trait_info), or simply ignore that such errors can occur?

        guest_group = self._get_guest_group(groupname, operator.get_entity_id())
        # the method raises exception if groupname is not defined

        if mobile and not (len(mobile) == 8 and mobile.isdigit()):
            raise CerebrumError('Invalid phone number, must be 8 digits')

        if responsible:
            if not self.ba.is_superuser(operator.get_entity_id()):
                raise PermissionDenied('Only superuser can set responsible')
            ac = self._get_account(responsible)
            responsible = ac.entity_id
        else:
            responsible = operator.get_entity_id()

        # Check the maximum number of guest accounts per user
        # TODO: or should we check per person instead?
        if not self.ba.is_superuser(operator.get_entity_id()):
            nr = len(tuple(self._get_guests(responsible))) 
            if nr > guestconfig.GUEST_MAX_PER_PERSON:
                self.logger.debug("More than %d guests, stopped" %
                                  guestconfig.GUEST_MAX_PER_PERSON)
                raise PermissionDenied('Not allowed to have more than '
                    '%d active guests, you have %d' % (guestconfig.GUEST_MAX_PER_PERSON, nr))

        end_date = DateTime.now() + days

        # Everything should now be okay, so we create the guest account
        ac = self._create_guest_account(responsible, end_date, fname, lname, mobile,
                                        guest_group)
        # Set the password
        password = ac.make_passwd(ac.account_name)
        ac.set_password(password)
        ac.write_db()

        if mobile:
            msg = guestconfig.GUEST_WELCOME_SMS % {'username': ac.account_name,
                                    'expire': end_date.strftime('%Y-%m-%d'),
                                    'password': password}

            sms = SMSSender(logger=self.logger)
            sms(mobile, msg)
        else:
            # TBD: is it okay to reuse 'user_passwd' and not create a new state?
            operator.store_state("user_passwd", {'account_id': int(ac.entity_id),
                                                 'password': password})
        return "Created guest account: %s" % ac.account_name

    def _create_guest_account(self, responsible_id, end_date, fname, lname,
                              mobile, guest_group):
        """Helper method for creating a guest account for a given responsible
        account. Note that this method does not validate any input, that must
        already have been done before calling this.

        @rtype:  Account
        @return: The created guest account

        """
        owner_group = self._get_owner_group()
        # Get all settings for the given guest type:
        settings = guestconfig.GUEST_TYPES[guest_group.group_name]

        ac = self.Account_class(self.db)
        name = ac.suggest_unames(self.const.account_namespace, fname, lname,
                                 maxlen=25, prefix=settings['prefix'],
                                 suffix='')[0]
        # TODO: make use of ac.create() instead, when it has been defined
        # properly.
        ac.populate(name = name, owner_type = self.const.entity_group,
                    owner_id = owner_group.entity_id,
                    np_type = self.const.account_guest, 
                    creator_id = responsible_id,
                    expire_date = None) # TODO: should we set expire_date to a
                                        # end_date + 5 (grace period)?
        ac.write_db()

        # Tag the account as a guest account:
        ac.populate_trait(code=self.const.trait_guest_owner,
                          target_id=responsible_id)
        # TODO; have to run write_db() here?

        # Save the guest's name:
        ac.populate_trait(code=self.const.trait_guest_name,
                          strval='%s %s' % (fname, lname))

        # Set the quarantine:
        ac.add_entity_quarantine(type=self.const.quarantine_guest_old,
                                 creator = responsible_id, 
                                 # TBD: or should creator be bootstrap_account?
                                 description = 'New guest account',
                                 start = end_date)

        # Add spreads
        for spr in settings.get('spreads', ()):
            try:
                spr = int(self.const.Spread(spr))
            except Errors.NotFoundError:
                self.logger.warn('Unknown guest spread: %s' % spr)
                continue
            ac.add_spread(spr)
        # TODO: write_db now?

        # TODO: log the guest create for both the responsible and the operator
        #self.log... for responsible
        #if operator.get_entity_id() != responsible:
        #    # self.log... for operator
        #    pass

        # Add guest account to correct group
        guest_group.add_member(ac.entity_id)
        # TODO: guest_group.write_db()?

        # Save the phone number
        if mobile:
            ac.add_contact_info(source=self.const.system_manual,
                                type=self.const.contact_mobile_phone,
                                value=mobile) # TODO: pref needed?
        ac.write_db()
        return ac

    # guest list
    all_commands['guest_list'] = Command(
        ("guest", "list"), AccountName(),
        fs=FormatSuggestion([('%-25s %-30s %-10s %-10s',
            ('username', 'name', format_day('created'), format_day('expires')))],
            hdr='%-25s %-30s %-10s %-10s' % ('Username', 'Name', 'Created', 'Expires'))
        )
    def guest_list(self, operator, entity):
        """Return a list of guest accounts that belongs to a given entity.
        """
        # TBD: change this to be able to get groups as owner too?
        account = self._get_account(entity)
        target_id = account.entity_id
        target_name = account.account_name

        ret = []
        for row in self._get_guests(target_id):
            account.clear()
            account.find(row['entity_id'])
            name = account.get_trait(self.const.trait_guest_name)['strval']
            q = account.get_entity_quarantine(self.const.quarantine_guest_old)
            end_date = q[0]['start_date']
            status = 'active'
            if end_date > DateTime.now():
                status = 'quarantined'
            ret.append({'username': account.account_name,
                        'created': account.create_date,
                        'expires': end_date,
                        'responsible': target_name,
                        'name': name,
                        'status': status})
        if not ret:
            raise CerebrumError("Found no guest accounts belonging to the user")
        return ret
