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
Abstract mapper for HR imports.

The mapper is responsible for translating the raw data from a datasource into
HR objects, as well as mapping external objects to local objects (e.g.  find a
Cerebrum.Person object from employee data).
"""
import abc

import six


class MapperError(RuntimeError):
    """ Unable to fetch data. """
    pass


class NoMappedObjects(MapperError):
    """ Unable to map object - no matches. """
    pass


class ManyMappedObjects(MapperError):
    """ Unable to map object - multiple matches. """
    pass


@six.add_metaclass(abc.ABCMeta)
class AbstractMapper(object):
    """
    Fetch objects from remote systems.
    """

    @abc.abstractmethod
    def translate(self, reference, obj):
        """
        Translate datasource into a remote object.

        :type reference: six.text_type
        :param reference:
            An object reference, as provided by
            :meth:`AbstractDatasource.get_reference`

        :type obj: object
        :param obj:
            An object, as provided by :meth:`AbstractDatasource.get_object`

        :rtype: models.HRPerson
        """
        pass

    @abc.abstractmethod
    def find_entity(self, hr_object):
        """
        Find a Cerebrum object/entity.

        :type hr_object: models.HRPerson
        :param obj:
            An object, as provided by :meth:`AbstractDatasource.get_object`

        :rtype: Cerebrum.Person.Person

        :raises NoMappedObjects: No entity can be found
        :raises ManyMappedObjects: Multiple entities can be found
        """
        pass
