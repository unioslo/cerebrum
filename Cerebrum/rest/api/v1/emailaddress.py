#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016 University of Oslo, Norway
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
""" E-mail address API """

from __future__ import unicode_literals

from flask_restx import Namespace, Resource, abort
from Cerebrum.rest.api import db, auth, fields, utils

from Cerebrum import Errors
from Cerebrum.modules import Email

api = Namespace('emailaddresses', description='Email address operations')


def find_email_address(address):
    """Looks up an email address.

    :param int/str address: Email address entity ID or FQDA
    :rtype Email.EmailAddress:
    :return: the email address object
    """
    ea = Email.EmailAddress(db.connection)
    lookup = ea.find_by_address
    if isinstance(address, (int, long)):
        lookup = ea.find
    try:
        lookup(address)
    except (Errors.NotFoundError, ValueError):
        abort(404, message="No such email address {}".format(address))
    return ea


def format_email_address(addr, et):
    target_entity_type = et.get_target_entity_type()
    if target_entity_type:
        target_entity_type = db.const.EntityType(target_entity_type)
    target_entity_name = None
    if target_entity_type == db.const.entity_account:
        target_entity_name = utils.get_entity_name(et.get_target_entity_id())
    return {
        'value': addr,
        'type': db.const.EmailTarget(et.get_target_type()),
        'target_entity_name': target_entity_name,
        'target_entity_type': target_entity_type,
    }


def find_email_target_by_address(ea):
    if not isinstance(ea, Email.EmailAddress):
        ea = find_email_address(ea)
    et = Email.EmailTarget(db.connection)
    et.find(ea.email_addr_target_id)
    return ea, et


def get_email_address(ea):
    ea, et = find_email_target_by_address(ea)
    return format_email_address(
        addr=ea.get_address(),
        et=et,
    )


def list_email_addresses(ea):
    ea, et = find_email_target_by_address(ea)
    return map(lambda (lp, dom, _a_id): format_email_address('{}@{}'.format(lp, dom), et),
               et.get_addresses())


EmailAddress = api.model('EmailAddress', {
    'value': fields.base.String(
        description='The email address'),
    'type': fields.base.String(
        description="Email address target type, i.e. 'forward', 'account"),
    'target_entity_type': fields.base.String(
        description="Email address target entity type"),
    'target_entity_name': fields.base.String(
        description="Email address target entity name"),
})

EmailAddresses = api.model('EmailAddresses', {
    'addresses': fields.base.List(
        fields.base.Nested(EmailAddress),
        description='List of addresses'),
})


@api.route('/<string:address>', endpoint='emailaddresses')
@api.doc(params={'address': 'Email address'})
class EmailAddressesResource(Resource):
    """Resource for listing email addresses."""
    @api.marshal_list_with(EmailAddress)
    @auth.require()
    def get(self, address):
        """Get email address information."""
        return get_email_address(address)
