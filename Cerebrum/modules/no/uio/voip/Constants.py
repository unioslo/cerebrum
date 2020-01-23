#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright 2010-2018 University of Oslo, Norway
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

"""This module defines various constants for the voip module.
"""


from Cerebrum import Constants
from Cerebrum.Constants import (_EntityTypeCode as EntityTypeCode,
                                _CerebrumCode, _AuthoritativeSystemCode,
                                _AuthenticationCode)


class _VoipServiceTypeCode(_CerebrumCode):
    """Different types of non-personal phone locations (voip_service)."""

    _lookup_table = '[:table schema=cerebrum name=voip_service_type_code]'
# end _VoipServiceTypeCode


class _VoipClientTypeCode(_CerebrumCode):
    """Different types of clients -- soft- and hardphones."""

    _lookup_table = '[:table schema=cerebrum name=voip_client_type_code]'
# end _VoipClientTypeCode


class _VoipClientInfoCode(_CerebrumCode):
    """Client models in voip -- i.e. a specific phone model string (Foo 123).
    """

    _lookup_table = '[:table schema=cerebrum name=voip_client_info_code]'
# end _VoipClientInfoCode


class _EntityAuthenticationCode(_CerebrumCode):
    """Code class for various authentication codes."""

    _lookup_table = '[:table schema=cerebrum name=entity_authentication_code]'
# end class _EntityAuthenticationCode


class VoipAuthConstants(Constants.Constants):
    """Authentication constants for voip."""

    EntityAuthenticationCode = _EntityAuthenticationCode

    voip_auth_sip_secret = _EntityAuthenticationCode(
        'voip-sipsecret',
        'sipSecret value for voip clients')

    auth_type_ha1_md5 = _AuthenticationCode(
        'HA1-MD5',
        "Used in digest access authentication as specified in RFC 2617. "
        "Is an unsalted MD5 digest hash over 'username:realm:password'. "
        "See <http://tools.ietf.org/html/rfc2617#section-3.2.2.2>")
# end VoipAuthConstants


class VoipConstants(Constants.Constants):
    VoipClientTypeCode = _VoipClientTypeCode
    VoipClientInfoCode = _VoipClientInfoCode
    VoipServiceTypeCode = _VoipServiceTypeCode

    ########################################################################
    # generic voip stuff
    system_voip = _AuthoritativeSystemCode('VOIP', 'Data from voip')

    ########################################################################
    # voip-service
    entity_voip_service = EntityTypeCode(
        "voip_service",
        "voipService - see module mod_voip.sql and friends"
        )

    voip_service_lab = VoipServiceTypeCode(
        "voip_service_lab",
        "lab",
        )

    voip_service_moterom = VoipServiceTypeCode(
        "voip_service_møterom",
        "møterom",
        )

    voip_service_resepsjon = VoipServiceTypeCode(
        "voip_service_resepsjon",
        "resepsjon",
        )

    voip_service_forening = VoipServiceTypeCode(
        "voip_service_forening",
        "forening",
        )

    voip_service_teknisk = VoipServiceTypeCode(
        "voip_service_teknisk",
        "teknisk",
        )

    voip_service_fellesnummer = VoipServiceTypeCode(
        "voip_service_fellesnummer",
        "fellesnummer",
        )

    voip_service_porttelefon = VoipServiceTypeCode(
        "voip_service_porttelefon",
        "porttelefon",
        )

    voip_service_fax = VoipServiceTypeCode(
        "voip_service_fax",
        "fax",
        )

    voip_service_ledig_arbeidsplass = VoipServiceTypeCode(
        "voip_service_ledig_arbeidsplass",
        "ledig arbeidsplass",
        )

    voip_service_heis = VoipServiceTypeCode(
        "voip_service_heis",
        "heis",
        )

    voip_service_svarapparat = VoipServiceTypeCode(
        "voip_service_svarapparat",
        "svarapparat",
    )

    voip_service_upersonlig_kontor = VoipServiceTypeCode(
        "voip_service_upersonlig_kontor",
        "upersonlig kontor",
    )

    voip_service_video = VoipServiceTypeCode(
        "voip_service_video",
        "videoenhet",
    )

    voip_service_viderekoblet = VoipServiceTypeCode(
        "voip_service_viderekoblet",
        "viderekoblet",
    )

    voip_service_tradlos = VoipServiceTypeCode(
        "voip_service_trådløs",
        "trådløs",
    )

    voip_service_calling = VoipServiceTypeCode(
        "voip_service_calling",
        "calling",
    )

    voip_service_autodial = VoipServiceTypeCode(
        "voip_service_autodial",
        "autodial",
    )

    ########################################################################
    # voip-client
    entity_voip_client = EntityTypeCode(
        'voip_client',
        'voipClient - see module mod_voip.sql and friends'
        )

    voip_client_type_softphone = VoipClientTypeCode(
        'voip_softphone',
        'softphone voip client (e.g. a laptop with software)'
        )

    voip_client_type_hardphone = VoipClientTypeCode(
        'voip_hardphone',
        'hardphone voip client (e.g. a physical device)'
        )

    # This is client info for softphones (there is no specific hardware
    # apparatus model to register here)
    voip_client_info_softphone = VoipClientInfoCode(
        "softphone",
        "softphone client"
        )

    voip_client_ip331 = VoipClientInfoCode(
        "001002",
        "Polycom IP331"
        )

    voip_client_vvx310 = VoipClientInfoCode(
        "001006",
        "Polycom VVX310"
        )

    voip_client_ip5000 = VoipClientInfoCode(
        "001007",
        "Polycom IP5000"
        )

    voip_client_ip6000 = VoipClientInfoCode(
        "001008",
        "Polycom IP6000"
        )

    voip_client_ip7000 = VoipClientInfoCode(
        "001009",
        "Polycom IP7000"
        )

    voip_client_vvx600 = VoipClientInfoCode(
        "001010",
        "Polycom VVX600"
        )

    voip_client_spa508g = VoipClientInfoCode(
        "002002",
        "Cisco SPA-508G"
        )

    voip_client_spa525g = VoipClientInfoCode(
        "002004",
        "Cisco SPA-525G"
        )

    voip_client_spa514g = VoipClientInfoCode(
        "002005",
        "Cisco SPA-514G"
        )

    voip_client_spa112 = VoipClientInfoCode(
        "002006",
        "Cisco SPA-112"
        )

    voip_client_spa232d = VoipClientInfoCode(
        "002007",
        "Cisco SPA-232D"
        )

    voip_client_pap2t = VoipClientInfoCode(
        "002008",
        "Linksys PAP2T"
    )

    voip_client_tcis6 = VoipClientInfoCode(
        "003001",
        "Zenitel TCIS-6"
    )

    voip_client_tciv3 = VoipClientInfoCode(
        "003002",
        "Zenitel TCIV-3"
    )

    voip_client_tciv6 = VoipClientInfoCode(
        "003003",
        "Zenitel TCIV-6"
    )

    voip_client_tcis3 = VoipClientInfoCode(
        "003004",
        "Zenitel TCIS-3"
    )

    voip_client_tkis2 = VoipClientInfoCode(
        "003005",
        "Zenitel TKIS-2"
    )

    voip_client_sx20 = VoipClientInfoCode(
        "004001",
        "Cisco SX-20"
    )

    voip_client_c40 = VoipClientInfoCode(
        "004002",
        "Cisco C40"
    )

    voip_client_c60 = VoipClientInfoCode(
        "004003",
        "Cisco C60"
    )

    voip_client_c90 = VoipClientInfoCode(
        "004004",
        "Cisco C90"
    )

    voip_client_sx80 = VoipClientInfoCode(
        "004005",
        "Cisco SX80"
    )

    ########################################################################
    # voip-address
    entity_voip_address = EntityTypeCode(
        'voip_address',
        'voipAddress - see module mod_voip.sql and friends'
        )

    contact_voip_extension = Constants.Constants.ContactInfo(
        'EXTENSION',
        'Extension number for voip (full and suffix)'
        )
# end VoipAddressConstants
