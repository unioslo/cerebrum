#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright 2010 University of Oslo, Norway
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

"""This module implements the necessary types to better support jbofh-bofhd
interaction for voip.
"""



import cereconf

from Cerebrum.modules.bofhd.cmd_param import Parameter


class MacAddress(Parameter):
    _type = "macAddress"
    _help_ref = "mac_address"
# end MacAddress


class VoipClientInfoCode(Parameter):
    _type = "voipClientInfoCode"
    _help_ref = "voip_client_info_code"
# end VoipClientInfoCode


class VoipClientTypeCode(Parameter):
    _type = "voipClientTypeCode"
    _help_ref = "voip_client_type_code"
# end voipClientTypeCode


class VoipServiceTypeCode(Parameter):
    _type = "voipService"
    _help_ref = "voip_service_type"
# VoipServiceTypeCode


class VoipAddressParameter(Parameter):
    _type = "voipAddress"
    _help_ref = "voip_address"


class VoipServiceParameter(Parameter):
    _type = "voipService"
    _help_ref = "voip_service"
    

class VoipOwnerParameter(Parameter):
    _type = "voipOwner"
    _help_ref = "voip_owner"


class PriorityParameter(Parameter):
    _type = "priority"
    _help_ref="priority"


class ContactTypeParameter(Parameter):
    _type = "contact_type"
    _help_ref = "contactType"

class VoipClientParameter(Parameter):
    _type = "voipClient"
    _help_ref = "voip_client"
