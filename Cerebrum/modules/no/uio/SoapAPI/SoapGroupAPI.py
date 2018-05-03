# -*- coding: utf-8 -*-
# Copyright 2014-2017 University of Oslo, Norway
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

"""Generalized SOAP interface for Cerebrums group functionality."""

from __future__ import unicode_literals

from Cerebrum.modules.cis import SoapListener, faults
from rpclib.model.primitive import Unicode, DateTime, Integer, Boolean
from rpclib.model.complex import Array
from rpclib.decorator import rpc

from Cerebrum.modules.no.uio.SoapAPI.SoapGroupAPImodel import (GroupInfo,
                                                               GroupMember)


NAMESPACE = 'GroupAPI'


class GroupAPIService(SoapListener.BasicSoapServer):
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

    @rpc(Unicode, Unicode, DateTime, Unicode,
         _throws=faults.EndUserFault, _returns=Integer)
    def group_create(ctx, group_name, description,
                     expire_date=None, visibility=None):
        return ctx.udc[NAMESPACE].group_create(
            group_name, description, expire_date, visibility)

    @rpc(Unicode, Unicode, Unicode, Unicode,
         _throws=faults.EndUserFault, _returns=Boolean)
    def group_add_member(ctx, group_id_type, group_id,
                         member_id_type, member_id):
        return ctx.udc[NAMESPACE].group_add_member(
            group_id_type, group_id, member_id_type, member_id)

    @rpc(Unicode, Unicode, Unicode, Unicode,
         _throws=faults.EndUserFault, _returns=Boolean)
    def group_remove_member(ctx, group_id_type, group_id,
                            member_id_type, member_id):
        return ctx.udc[NAMESPACE].group_remove_member(
            group_id_type, group_id, member_id_type, member_id)

    @rpc(Unicode, Unicode,
         _throws=faults.EndUserFault, _returns=GroupInfo)
    def group_info(ctx, group_id_type, group_id):
        return ctx.udc[NAMESPACE].group_info(
            group_id_type, group_id)

    @rpc(Unicode, Unicode,
         _throws=faults.EndUserFault, _returns=Array(GroupMember))
    def group_list(ctx, group_id_type, group_id):
        return ctx.udc[NAMESPACE].group_list(group_id_type, group_id)

    @rpc(Unicode, Unicode, DateTime, _throws=faults.EndUserFault)
    def group_set_expire(ctx, group_id_type, group_id, expire_date=None):
        return ctx.udc[NAMESPACE].group_set_expire(group_id_type,
                                                   group_id,
                                                   expire_date)
