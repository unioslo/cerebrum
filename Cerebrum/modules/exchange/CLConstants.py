# -*- coding: utf-8 -*-
# Copyright 2014 University of Oslo, Norway
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

"""ChangeLog constants for Exchange."""

from Cerebrum.modules.CLConstants import CLConstants
from Cerebrum.modules.CLConstants import _ChangeTypeCode


class CLConstants(CLConstants):

    """ChangeLog constants for Exchange."""

    # TODO: Clean up these codes! Some are unused, some are a bit wrongly named
    # exchange-relatert-jazz
    #
    # changelog variables used by the EventHandler to register
    # when events are handled by the recieving system
    #

    # Temporary hack, we need this in order to requeue the setting of
    # the adress book policy for a mailbox if someone pulls the plug on
    # one of the Exchange-servers at exactly the right time.
    # Ask jsama about this.
    ea_policy = _ChangeTypeCode('exchange', 'set_ea_policy',
                                'Address book policy changed')
    # SingleItemRecoveryEnabled
    # Fake event to be able to requeue if fail
    item_recovery = _ChangeTypeCode('exchange', 'item_recovery',
                                    'Set SingleItemRecovery')

    # Account mailbox created/deleted
    acc_mbox_create = _ChangeTypeCode('exchange', 'acc_mbox_create',
                                      'account mailbox added')
    acc_mbox_delete = _ChangeTypeCode('exchange', 'acc_mbox_delete',
                                      'account mailbox deleted')
    # Account add/remove an address
    acc_addr_add = _ChangeTypeCode('exchange', 'acc_addr_add',
                                   'account address added')
    acc_addr_rem = _ChangeTypeCode('exchange', 'acc_addr_rem',
                                   'account address removed')
    # Account change primary address
    acc_primaddr = _ChangeTypeCode('exchange', 'acc_primaddr',
                                   'account primary changed')
    # Electronic reservation registered
    pers_reservation = _ChangeTypeCode(
        'exchange', 'per_e_reserv',
        'address book visibility changed', ('visible = %(string:visible)s',))

    # Distribution group create/deleted
    dl_mbox_create = _ChangeTypeCode('exchange', 'dl_mbox_create',
                                     'dist group mailbox added')
    dl_mbox_delete = _ChangeTypeCode('exchange', 'dl_mbox_delete',
                                     'dist group mailbox deleted')
    # Dist group add/remove address
    dl_addr_add = _ChangeTypeCode('exchange', 'dl_addr_add',
                                  'dist group address added')
    dl_addr_rem = _ChangeTypeCode('exchange', 'dl_addr_rem',
                                  'dist group address deleted')
    # Dist group set managed by
    dl_manby_set = _ChangeTypeCode('exchange', 'dl_manby_set',
                                   'dist group set Managedby')
    # Dist group set moderated by
    dl_modby_set = _ChangeTypeCode('exchange', 'dl_modby_set',
                                   'dist group set Moderatedby')
    # Dist group set hidden
    dl_hidden_set = _ChangeTypeCode('exchange', 'dl_hidden_set',
                                    'dist group set HiddenAddr')
    # Dist group set join/depart restrictions
    dl_join_set = _ChangeTypeCode('exchange', 'dl_join_set',
                                  'dist group set JoinRestr')
    dl_depart_set = _ChangeTypeCode('exchange', 'dl_depart_set',
                                    'dist group set DepartRestr')

    # register when a distribution group has been created or removed
    # should probably log and show more data about groups
    dl_group_create = _ChangeTypeCode('dlgroup', 'create',
                                      'group create distribution %(subject)s')
    dl_group_modify = _ChangeTypeCode('dlgroup', 'modify',
                                      'group modify distribution %(subject)s')
    dl_group_remove = _ChangeTypeCode('dlgroup', 'remove',
                                      'group remove distribution %(subject)s')

    dl_group_add = _ChangeTypeCode(
        'dlgroup', 'add', 'added %(subject)s to %(dest)s',
        ('AlreadyPerformed=%(string:AlreadyPerformed)s',))
    dl_group_rem = _ChangeTypeCode('dlgroup', 'rem',
                                   'removed %(subject)s from %(dest)s')

    dl_group_primary = _ChangeTypeCode('dlgroup', 'primary',
                                       'group set primary for %(subject)s')
    dl_group_addaddr = _ChangeTypeCode('dlgroup', 'addaddr',
                                       'group add address for %(subject)s')
    dl_group_remaddr = _ChangeTypeCode('dlgroup', 'remaddr',
                                       'group remove address for %(subject)s')
    dl_roomlist_create = _ChangeTypeCode('dlgroup', 'roomcreate',
                                         'group create roomlist %(subject)s')
    dl_group_hidden = _ChangeTypeCode('dlgroup', 'modhidden',
                                      'group mod hidden for %(subject)s',
                                      ('hidden:%(string:hidden)'))
    dl_group_depres = _ChangeTypeCode('dlgroup',
                                      'moddepres',
                                      'group mod dep restriction for '
                                      '%(subject)s',
                                      ('deprestr:%(string:deprestr)'))
    dl_group_joinre = _ChangeTypeCode('dlgroup',
                                      'modjoinre',
                                      'group mod join restriction for '
                                      '%(subject)s',
                                      ('joinrestr:%(string:joinrestr)'))
    dl_group_manby = _ChangeTypeCode('dlgroup', 'modmanby',
                                     'group mod managed by for %(subject)s',
                                     ('manby:%(str:manby)'))
    dl_group_modby = _ChangeTypeCode('dlgroup', 'modmodby',
                                     'group mod modify by for %(subject)s',
                                     ('modby:%(str:modby)'))
    dl_group_room = _ChangeTypeCode('dlgroup', 'modroom',
                                    'group mod room stat for %(subject)s',
                                    ('roomlist:%(str:roomlist)'))
    dl_group_modrt = _ChangeTypeCode('dlgroup', 'moderate',
                                     'group mod room stat for %(subject)s',
                                     ('modenable:%(str:enable)'))
