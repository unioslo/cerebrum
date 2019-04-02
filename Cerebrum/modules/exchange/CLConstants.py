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
    acc_mbox_create = cereconst._ChangeTypeCode('exchange', 'acc_mbox_create',
                                                'account mailbox added')
    acc_mbox_delete = cereconst._ChangeTypeCode('exchange', 'acc_mbox_delete',
                                                'account mailbox deleted')

    # Account mailbox created/deleted
    shared_mbox_create = cereconst._ChangeTypeCode('exchange',
                                                   'shared_mbox_create',
                                                   'shared mailbox added')
    shared_mbox_delete = cereconst._ChangeTypeCode('exchange',
                                                   'shared_mbox_delete',
                                                   'shared mailbox deleted')

    # Account add/remove an address
    acc_addr_add = cereconst._ChangeTypeCode('exchange', 'acc_addr_add',
                                             'account address added')
    acc_addr_rem = cereconst._ChangeTypeCode('exchange', 'acc_addr_rem',
                                             'account address removed')
    # Account change primary address
    acc_primaddr = cereconst._ChangeTypeCode('exchange', 'acc_primaddr',
                                             'account primary changed')

    # Setting of local delivery
    acc_local_delivery = cereconst._ChangeTypeCode(
        'exchange', 'local_delivery',
        'local delivery setting changed', ('enabled = %(string:enabled)s',))

    # Electronic reservation registered
    pers_reservation = cereconst._ChangeTypeCode(
        'exchange', 'per_e_reserv',
        'address book visibility changed', ('visible = %(string:visible)s',))

    # register when a distribution group has been created or removed
    # should probably log and show more data about groups
    dl_group_create = cereconst._ChangeTypeCode(
        'dlgroup', 'create', 'group create distribution %(subject)s')
    dl_group_modify = cereconst._ChangeTypeCode(
        'dlgroup', 'modify', 'group modify distribution %(subject)s')
    dl_group_remove = cereconst._ChangeTypeCode(
        'dlgroup', 'remove', 'group remove distribution %(subject)s')

    dl_group_add = cereconst._ChangeTypeCode(
        'dlgroup', 'add', 'added %(dest)s to %(subject)s',
        ('AlreadyPerformed=%(string:AlreadyPerformed)s',))
    dl_group_rem = cereconst._ChangeTypeCode(
        'dlgroup', 'rem', 'removed %(dest)s from %(subject)s')

    dl_group_primary = cereconst._ChangeTypeCode(
        'dlgroup', 'primary', 'group set primary for %(subject)s')
    dl_group_addaddr = cereconst._ChangeTypeCode(
        'dlgroup', 'addaddr', 'group add address for %(subject)s')
    dl_group_remaddr = cereconst._ChangeTypeCode(
        'dlgroup', 'remaddr', 'group remove address for %(subject)s')
    dl_roomlist_create = cereconst._ChangeTypeCode(
        'dlgroup', 'roomcreate', 'group create roomlist %(subject)s')
    dl_group_hidden = cereconst._ChangeTypeCode(
        'dlgroup', 'modhidden', 'group mod hidden for %(subject)s',
        ('hidden:%(string:hidden)'))
    dl_group_manby = cereconst._ChangeTypeCode(
        'dlgroup', 'modmanby', 'group mod managed by for %(subject)s',
        ('manby:%(str:manby)'))
    dl_group_room = cereconst._ChangeTypeCode(
        'dlgroup', 'modroom', 'group mod room stat for %(subject)s',
        ('roomlist:%(str:roomlist)'))

    # deferred events
    exchange_group_add = cereconst._ChangeTypeCode(
        'exchange', 'group_add', 'deferred addition of group member')

    exchange_group_rem = cereconst._ChangeTypeCode(
        'exchange', 'group_rem', 'deferred removal of group member')
