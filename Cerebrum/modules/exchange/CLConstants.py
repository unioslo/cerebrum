#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2014-2016 University of Oslo, Norway
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

from Cerebrum import Constants as cereconst


class CLConstants(cereconst.CLConstants):

    """ChangeLog constants for Exchange."""

    # TODO: Clean up these codes! Some are unused, some are a bit wrongly named
    # exchange-relatert-jazz
    #
    # changelog variables used by the EventHandler to register
    # when events are handled by the recieving system
    #

    # Account mailbox created/deleted
    acc_mbox_create = cereconst._ChangeTypeCode('exchange_acc_mbox', 'create',
                                                'account mailbox added')
    acc_mbox_delete = cereconst._ChangeTypeCode('exchange_acc_mbox', 'delete',
                                                'account mailbox deleted')

    # Account mailbox created/deleted
    shared_mbox_create = cereconst._ChangeTypeCode('exchange_shared_mbox',
                                                   'create',
                                                   'shared mailbox added')
    shared_mbox_delete = cereconst._ChangeTypeCode('exchange_shared_mbox',
                                                   'delete',
                                                   'shared mailbox deleted')

    # Account add/remove an address
    acc_addr_add = cereconst._ChangeTypeCode('exchange_acc_addr', 'add',
                                             'account address added')
    acc_addr_rem = cereconst._ChangeTypeCode('exchange_acc_addr', 'remove',
                                             'account address removed')
    # Account change primary address
    acc_primaddr = cereconst._ChangeTypeCode('exchange_acc_primaddr', 'set',
                                             'account primary changed')

    # Setting of local delivery
    acc_local_delivery = cereconst._ChangeTypeCode(
        'exchange_local_delivery', 'set',
        'local delivery setting changed', ('enabled = %(string:enabled)s',))

    # Electronic reservation registered
    pers_reservation = cereconst._ChangeTypeCode(
        'exchange_per_e_reserv', 'set',
        'address book visibility changed', ('visible = %(string:visible)s',))

    # register when a distribution group has been created or removed
    # should probably log and show more data about groups
    dl_group_create = cereconst._ChangeTypeCode(
        'dlgroup', 'create', 'group create distribution %(subject)s')
    dl_group_modify = cereconst._ChangeTypeCode(
        'dlgroup', 'modify', 'group modify distribution %(subject)s')
    dl_group_remove = cereconst._ChangeTypeCode(
        'dlgroup', 'delete', 'group remove distribution %(subject)s')

    dl_group_add = cereconst._ChangeTypeCode(
        'dlgroup_member', 'add', 'added %(dest)s to %(subject)s',
        ('AlreadyPerformed=%(string:AlreadyPerformed)s',))
    dl_group_rem = cereconst._ChangeTypeCode(
        'dlgroup_member', 'remove', 'removed %(dest)s from %(subject)s')

    dl_group_primary = cereconst._ChangeTypeCode(
        'dlgroup_primary', 'set', 'group set primary for %(subject)s')
    dl_group_addaddr = cereconst._ChangeTypeCode(
        'dlgroup_addr', 'add', 'group add address for %(subject)s')
    dl_group_remaddr = cereconst._ChangeTypeCode(
        'dlgroup_addr', 'remove', 'group remove address for %(subject)s')
    dl_roomlist_create = cereconst._ChangeTypeCode(
        'dlgroup_room', 'create', 'group create roomlist %(subject)s')
    dl_group_hidden = cereconst._ChangeTypeCode(
        'dlgroup_hidden', 'modify', 'group mod hidden for %(subject)s',
        'hidden:%(string:hidden)')
    dl_group_manby = cereconst._ChangeTypeCode(
        'dlgroup_manager', 'set', 'group mod managed by for %(subject)s',
        'manby:%(str:manby)')
    dl_group_room = cereconst._ChangeTypeCode(
        'dlgroup_room', 'modify', 'group mod room stat for %(subject)s',
        'roomlist:%(str:roomlist)')

    # deferred events
    exchange_group_add = cereconst._ChangeTypeCode(
        'exchange_group_member', 'add', 'deferred addition of group member')

    exchange_group_rem = cereconst._ChangeTypeCode(
        'exchange_group_member', 'remove', 'deferred removal of group member')
