# -*- coding: utf-8 -*-
# Copyright 2005 University of Oslo, Norway
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
from __future__ import unicode_literals
from six import python_2_unicode_compatible


@python_2_unicode_compatible
class DataEntity(object):
    """Class for representing common traits of objects in a data source."""

    def __init__(self):
        self._ids = dict()
        self._tags = dict()
        self._names = dict()
        self._address = dict()
        self._contacts = dict()

    def __str__(self):
        addr = dict()
        for a, v in self.iteraddress():
            addr[a] = v.__str__()
        return ("DataEntity: IDs: {} tags: {} names: {} "
                "address: {} contacts: {}").format(
            (list(self.iterids()),
             list(self.itertags()),
             list(self.iternames()),
             list(addr.items()),
             list(self.itercontacts())))

    def add_id(self, kind, value):
        self._ids[kind] = value

    def add_tag(self, kind, value):
        if kind == None:
            return
        self._tags.setdefault(kind, []).append(value)

    def add_name(self, kind, value):
        self._names[kind] = value

    def add_address(self, kind, value):
        self._address[kind] = value

    def add_contact(self, kind, value):
        self._contacts[kind] = value

    def iterids(self):
        return self._ids.items()

    def itertags(self):
        return self._tags.items()

    def iternames(self):
        return self._names.items()

    def iteraddress(self):
        return self._address.items()

    def itercontacts(self):
        return self._contacts.items()


class DataPerson(DataEntity):
    """Class for representing people in a data source."""

    def __init__(self):
        super(DataPerson, self).__init__()
        self.birth_date = None
        self.gender = None

    def __str__(self):
        return "{} DataPerson: gender: {} birth: {}".format(
            super(DataPerson, self).__str__(),
            self.gender, self.birth_date
        )


@python_2_unicode_compatible
class DataOU(DataEntity):
    """Class for representing OUs."""

    def __init__(self):
        super(DataOU, self).__init__()
        # Following variable(s) are for organization only.
        self.realm = None
        self.ou = None
        # Following variable(s) are for OU only.
        self.parent = None

    def __str__(self):
        result = ("{} DataOU: trealm: {} parent: {}".format(
            super(DataOU, self).__str__(),
            self.realm, self.parent)
        )
        return result


@python_2_unicode_compatible
class DataGroup(DataEntity):
    """Class for representing Groups."""

    def __init__(self):
        super(DataGroup, self).__init__()
        self.desc = None

    def __str__(self):
        return "{} DataGroup: desc: {}".format(
            super(DataGroup, self).__str__(),
            self.desc
        )


@python_2_unicode_compatible
class DataRelation(DataEntity):
    """Class for representing Relations."""

    def __init__(self):
        super(DataRelation, self).__init__()
        self.type = None
        self.subject = None
        self.object = None

    def __str__(self):
        return "{} DataRelation: type: {} subject: {} object: {}".format(
            super(DataRelation, self).__str__(),
            self.type, self.subject, self.object
        )


@python_2_unicode_compatible
class DataAddress(object):
    """Class for represening Addresses."""

    def __init__(self):
        self.pobox = None
        self.street = None
        self.postcode = None
        self.city = None
        self.country = None

    def __str__(self):
        return "pobox: {}, street: {}, postcode: {}, city: {}, country: {}".format(
            self.pobox, self.street,
            self.postcode, self.city,
            self.country
        )
