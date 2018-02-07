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
        for a,v in self.iteraddress():
            addr[a] = v.__str__()
        result = ("DataEntity: IDs: %s tags: %s names: %s address: %s contacts: %s" %
                  (list(self.iterids()),
                   list(self.itertags()),
                   list(self.iternames()),
                   list(addr.iteritems()),
                   list(self.itercontacts())))
        return result

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
        return self._ids.iteritems()

    def itertags(self):
        return self._tags.iteritems()

    def iternames(self):
        return self._names.iteritems()

    def iteraddress(self):
        return self._address.iteritems()

    def itercontacts(self):
        return self._contacts.iteritems()


class DataPerson(DataEntity):
    """Class for representing people in a data source."""

    def __init__(self):
        super(DataPerson, self).__init__()
        self.birth_date = None
        self.gender = None

    def __str__(self):
        result = ("%s DataPerson: gender: %s birth: %s" %
                  (super(DataPerson, self).__str__(),
                   self.gender, self.birth_date))
        return result



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
        result = ("%s DataOU: trealm: %s parent: %s" %
                  (super(DataOU, self).__str__(),
                   self.realm, self.parent))
        return result

class DataGroup(DataEntity):
    """Class for representing Groups."""

    def __init__(self):
        super(DataGroup, self).__init__()
        self.desc = None

    def __str__(self):
        result = ("%s DataGroup: desc: %s" %
                  (super(DataGroup, self).__str__(),
                   self.desc))
        return result


class DataRelation(DataEntity):
    """Class for representing Relations."""

    def __init__(self):
        super(DataRelation, self).__init__()
        self.type = None
        self.subject = None
        self.object = None

    def __str__(self):
        result = ("%s DataRelation: type: %s subject: %s object: %s" %
                  (super(DataRelation, self).__str__(),
                   self.type, self.subject, self.object))
        return result


class DataAddress(object):
    """Class for represening Addresses."""

    def __init__(self):
        self.pobox = None
        self.street = None
        self.postcode = None
        self.city = None
        self.country = None

    def __str__(self):
        result = ("pobox: %s, street: %s, postcode: %s, city: %s, country: %s" %
                  (self.pobox, self.street,
                   self.postcode, self.city,
                   self.country))
        return result

