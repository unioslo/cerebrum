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

"""Generalized SOAP interface for Cerebrums Entity functionality."""

from Cerebrum.modules.cis import SoapListener, faults
from rpclib.model.primitive import Unicode, Boolean
from rpclib.model.complex import Array
from rpclib.decorator import rpc

NAMESPACE = 'EntityAPI'


class EntityAPIService(SoapListener.BasicSoapServer):
    """Function definitions for the service."""
    __namespace__ = NAMESPACE
    __tns__ = NAMESPACE

    # Require the session ID in the client's header
    __in_header__ = SoapListener.SessionHeader
    # Respond with a header with the current session ID
    __out_header__ = SoapListener.SessionHeader

    # The class where the Cerebrum-specific functionality is done. This is
    # instantiated per call, to avoid thread conflicts.
    cere_class = None

    # The hook for the site object
    site = None

    @rpc(Unicode, Unicode, _throws=faults.EndUserFault,
         _returns=Array(Unicode))
    def spread_list(ctx, id_type, entity_id):
        return ctx.udc[NAMESPACE].spread_list(id_type, entity_id)

    @rpc(Unicode, Unicode, Unicode, _throws=faults.EndUserFault,
         _returns=Boolean)
    def in_system(ctx, id_type, entity_id, system):
        return ctx.udc[NAMESPACE].in_system(id_type, entity_id, system)

    @rpc(Unicode, Unicode, Unicode, _throws=faults.EndUserFault,
         _returns=Boolean)
    def active_in_system(ctx, id_type, entity_id, system):
        return ctx.udc[NAMESPACE].active_in_system(id_type, entity_id, system)

    @rpc(Unicode, Unicode, Unicode, _throws=faults.EndUserFault)
    def add_to_system(ctx, id_type, entity_id, system):
        return ctx.udc[NAMESPACE].add_to_system(id_type, entity_id, system)
