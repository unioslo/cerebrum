# -*- coding: utf-8 -*-
#
# Copyright 2020 University of Oslo, Norway
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
Abstract datasource for HR imports.

The datasource is responsible for parsing events (messages) and fetching data
from a given source system.
"""
import abc
import collections

import six


class DatasourceError(RuntimeError):
    """ Unable to fetch data. """
    pass


class DatasourceUnavailable(DatasourceError):
    """ Unable to get data from data source. """
    pass


class DatasourceInvalid(DatasourceError):
    """ Got broken data from data source. """
    pass


class RemoteObject(collections.Mapping):

    def __init__(self, source, reference, data):
        self.src = source
        self.ref = reference
        self._data = data

    def __repr__(self):
        return '<{c.__name__} src={o.src} ref={o.ref} at 0x{a:x}>'.format(
            c=type(self),
            o=self,
            a=id(self),
        )

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    def __getitem__(self, item):
        return self._data[item]


@six.add_metaclass(abc.ABCMeta)
class AbstractDatasource(object):
    """
    Fetch objects from remote systems.
    """

    @abc.abstractmethod
    def get_reference(self, event):
        """
        Extracts a reference or identifier from an event.

        :type event: Cerebrum.modules.amqp.handlers.Event
        :param event:
            A notification that contains a reference to the modified object.

        :rtype: six.text_type
        :returns:
            Returns some reference or object identifier.  The value depends on
            the source system, but should be usable with :meth:`.get_object`

        :raises DatasourceInvalid: If the event is malformed.
        """
        pass

    @abc.abstractmethod
    def get_object(self, reference):
        """
        Fetch an object by reference/identifier.

        :type reference: six.text_type
        :param reference:
            An object reference, as returned by :meth:`.get_reference`.

        :rtype: object
        :returns:
            All relevant object data.  The type and format of the returned
            object depends on the source system.

        :raises DatasourceUnavailable:
            If the reference cannot be fetched from the source system (e.g.
            HTTP 5xx, connection error, missing mandatory headers).

        :raises DatasourceInvalid:
            If the source data is available, but a valid object cannot be built
            from the provided data.
        """
        # TODO: If we remove all db-interaction from `.mapper`, we may want to
        #       apply the mapper and return a `.models` object here!
        #       Note also that the is_active() and needs_delay() checks would
        #       have to be updated to look at an object from `.models`.
        pass

    @abc.abstractmethod
    def needs_delay(self, obj):
        """
        Examine object and decide additional future date triggers.

        Some changes are *future* updates that needs additional processing at a
        given date.  This method examines an object and returns a list of
        date or datetime objects for this purpose.

        These dates should be stored in a queue along with the original
        message or object reference, and re-processed at a later time.

        :type obj: object
        :param obj:
            An object, as provided by :meth:`.get_object`

        :rtype: list
        :returns:
            A list of date or datetime objects for future processing.
        """
        pass
