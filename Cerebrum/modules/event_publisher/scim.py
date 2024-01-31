# -*- coding: utf-8 -*-
#
# Copyright 2016-2023 University of Oslo, Norway
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
Implementation of SCIM messages.

See `<https://tools.ietf.org/html/draft-hunt-idevent-scim-00#section-2.2>`_ for
more info.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import uuid

import six

from Cerebrum.config.configuration import (
    Configuration,
    ConfigDescriptor,
    Namespace,
)
from Cerebrum.config.settings import String
from Cerebrum.utils import date as date_utils
from Cerebrum.utils import http as http_utils
from Cerebrum.utils import text_compat


class EntityTypeToApiRouteMapConfig(Configuration):
    """Configuration for Entity Type -> API Route"""

    entity = ConfigDescriptor(
        String,
        default='entities',
        doc='API Route for entities')

    person = ConfigDescriptor(
        String,
        default='persons',
        doc='API Route for person entities')

    account = ConfigDescriptor(
        String,
        default='accounts',
        doc='API Route for account entities')

    group = ConfigDescriptor(
        String,
        default='groups',
        doc='API Route for group entities')

    ou = ConfigDescriptor(
        String,
        default='ous',
        doc='API Route for OU entities')


class ScimFormatterConfig(Configuration):
    """Configuration for scim events"""

    issuer = ConfigDescriptor(
        String,
        default='cerebrum',
        doc='Issuer field in scim')

    urltemplate = ConfigDescriptor(
        String,
        default='https://cerebrum.example.com/v1/{entity_type}/{entity_id}',
        doc='Format string for URL (use {entity_type} and {entity_id} as '
            'placeholders')

    keytemplate = ConfigDescriptor(
        String,
        default='no.uio.cerebrum.scim.{entity_type}.{event}',
        doc=('Format string for routing key (use {entity_type} and {event} '
             'as placeholders'))

    entity_type_map = ConfigDescriptor(
        Namespace,
        config=EntityTypeToApiRouteMapConfig)

    uri_prefix = ConfigDescriptor(
        String,
        default='urn:ietf:params:event:SCIM',
        doc='Default URI Prefix for SCIM-events'
    )


class ScimFormatter(object):

    def __init__(self, config=None):
        self.config = config or ScimFormatterConfig()

    @staticmethod
    def make_timestamp(dt_object=None):
        """ Make a timestamp from a datetime object. """
        if dt_object is None:
            dt_object = date_utils.utcnow()
        return int(date_utils.to_timestamp(dt_object))

    def get_entity_type_route(self, entity_type):
        """ Get the API route for the given entity type. """
        default = self.config.entity_type_map.entity
        return getattr(self.config.entity_type_map, entity_type, default)

    def build_url(self, entity_type, entity_id):
        return self.config.urltemplate.format(
            entity_type=http_utils.safe_path(entity_type),
            entity_id=http_utils.safe_path(entity_id),
        )

    def get_uri(self, action):
        """ Format an uri for the message. """
        return '{}:{}'.format(self.config.uri_prefix,
                              text_compat.to_text(action))

    def get_key(self, entity_type, event):
        return self.config.keytemplate.format(
            entity_type=text_compat.to_text(entity_type),
            event=text_compat.to_text(event),
        )


class EventScimFormatter(ScimFormatter):
    """ Generate SCIM payload from Event objects. """

    def __init__(self, config=None):
        super(EventScimFormatter, self).__init__(config)

    def get_entity_type(self, entity_ref):
        """ Get and translate the entity_type of an EntityRef. """
        return super(EventScimFormatter, self).get_entity_type_route(
            entity_ref.entity_type
        )

    @staticmethod
    def get_entity_id(entity_ref):
        """ Get and translate the entity_id of an EntityRef. """
        if entity_ref.entity_type in ('account', 'group'):
            return entity_ref.ident
        return six.text_type(entity_ref.entity_id)

    def get_url(self, entity_ref):
        """ Format an url to the EntityRef. """
        entity_type = self.get_entity_type(entity_ref)
        entity_id = self.get_entity_id(entity_ref)
        return self.build_url(entity_type, entity_id)

    def get_key(self, event_type, entity_ref):
        """ Format a event key from the Event and EntityRef. """
        entity_type = self.get_entity_type(entity_ref)
        return super(EventScimFormatter, self).get_key(
            entity_type=entity_type,
            event=event_type.verb)

    def __call__(self, event):
        """Create and return payload as jsonable dict."""
        jti = six.text_type(uuid.uuid4())
        event_uri = self.get_uri(event.event_type.verb)
        issued_at = self.make_timestamp(event.timestamp)
        issuer = self.config.issuer
        audience = event.context
        subject = self.get_url(event.subject)

        payload = {
            'jti': jti,
            'eventUris': [event_uri, ],
            'iat': issued_at,
            'iss': issuer,
            'aud': list(audience),
            'sub': subject,
        }
        if event.attributes:
            payload.setdefault(
                event_uri,
                dict())['attributes'] = list(event.attributes)
        if event.objects:
            payload.setdefault(
                event_uri,
                dict())['object'] = [self.get_url(o) for o in event.objects]
        if event.scheduled is not None:
            # assume datetime.datetime, although mx-like datetime objects will
            # also work
            payload['nbf'] = self.make_timestamp(event.scheduled)
        payload['resourceType'] = self.get_entity_type(event.subject)
        return payload
