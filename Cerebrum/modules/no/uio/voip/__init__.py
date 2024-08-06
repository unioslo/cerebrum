# -*- encoding: utf-8 -*-
#
# Copyright 2010-2024 University of Oslo, Norway
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
"""
The VoIP modules for UiO.

This module and its submodules adds support for keeping VoIP data in Cerebrum.

Overview
---------
The goal of this module is mainly to provide data and utils for the LDIF file
generated by ``contrib/no/uio/generate_voip_ldif.py``.

The :class:``.bofhd_voip_cmds.BofhdVoipCommands` bofhd command module provides
commands and business logic for managing voip data.


Data model
----------
The voip submodules implements a series of new Entities: VoipClient,
VoipAddress, and VoipService.  The relationship between these entities are:
::

   VoipClient ---[belongs to]---+
                                |
              +-----------------+
              |
              +--> VoipAddress ---[owned by]---> Person or VoipService


:class:`.voipClient.VoipClient`
    The VoipClient represents one actual client.

    Each client is divided into two different ``client_type`` values — either a
    software client, or a hardware client (a physical phone).  Hardware phones
    needs a model number in the ``client_info`` attribute, as well as a
    well-formatted ``mac_address`` ("aa:bb:...").

    Each client also have a *sip secret* in the voip specific
    ``entity_authentication_info`` table.

:class:`.voipAddress.VoipAddress`
    Abstract object to represent a client owner.

    The owner itself can either be an actual *person*, or a *voipService*.  The
    *VoipAddress* binds the *VoipClient* to the owner, and provides an abstract
    API to get specific data from either owner type, like sip addresses.

:class:`.voipService.VoipService`
    The VoipService is an abstract entity to represent non-personal voip phones
    (e.g. meeting rooms, info desks).

    Each service is bound to an *org-unit* responsible for the service, and has
    a ``description`` and ``service_type`` category.


Voip data
---------
The voip module relies on some other entity mixins to store voip data:

Addresses
    Actual sip addresses are stored as regular contact info entries on the voip
    address *owner* - i.e. a VoipService or Person.  The VopiModule provides a
    single new contact info type - the EXTENSION.

Authentication
    Accounts may have a HA1-MD5 (HTTP Digest) secret for use with the voip
    system.
    This is provided by the :class:`.VoipAuthAccountMixin.VoipAuthAccountMixin`
    account mixin.

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)


# database schema version (mod_voip)
__version__ = "1.0"
