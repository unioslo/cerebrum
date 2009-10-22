# -*- coding: iso-8859-1 -*-
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

import sys
import time
from mx.DateTime import Date

import abcconf

from Cerebrum.modules.abcenterprise.ABCUtils import ABCTypes
from Cerebrum.modules.abcenterprise.ABCUtils import ABCTypesError
from Cerebrum.modules.abcenterprise.ABCUtils import ABCFactory
from Cerebrum.modules.abcenterprise.ABCDataObjects import DataGroup
from Cerebrum.modules.abcenterprise.ABCDataObjects import DataRelation
from Cerebrum.modules.abcenterprise.ABCDataObjects import DataAddress
from Cerebrum.modules.abcenterprise.ABCXmlParsers import XMLOrg2Object
from Cerebrum.modules.abcenterprise.ABCXmlParsers import XMLOU2Object
from Cerebrum.modules.abcenterprise.ABCXmlParsers import XMLPerson2Object


from Cerebrum.modules.no.ntnu.abcenterprise.ABCDataObjectsMixin import DataPersonMixin
from Cerebrum.modules.no.ntnu.abcenterprise.ABCDataObjectsMixin import DataOUMixin


class XMLOrg2ObjectMixIn(XMLOrg2Object):
    """A converter class that maps ElementTree's Element to DataOU.
    An Organization is represented as an OU."""

    def __init__(self, xmliter):
        """Constructs an iterator supplying DataPerson objects."""

        super(XMLOrg2ObjectMixIn, self).__init__(xmliter)

    def next(self):
        """Return the next DataOU object. Returns a ABCTypesError
        exception if object has errors in types. These objects should be
        skipped.

        Consume the next XML-element describing an organization, and
        return a suitable representation (DataOU).
        """

        # This call with propagate StopIteration when all the (XML) elements
        # are exhausted.
        element = super(XMLOrg2Object, self).next()
        result = DataOUMixin()
        
        # Iterate over *all* subelements
        for sub in element:
            value = None
            if sub.text:
                value = sub.text.strip().encode("latin1")

            if sub.tag == "orgid":
                if len(sub.attrib) <> 1:
                    raise ABCTypesError, "wrong number of arguments: %s" % value
                type = sub.attrib.get("orgidtype")
                ## FIXME: *very*, *very* ugly...
                if type == 'stedkode':
                    result.stedkodes.append(value)
                else:
                    result.add_id(ABCTypes.get_type("orgidtype",(type,)),
                              value)
            elif sub.tag == "orgname":
                if len(sub.attrib) <> 2:
                    raise ABCTypesError, "not 2 attributes: %s" % value
                type = sub.attrib.get("orgnametype")
                # TODO: support lang
                lang = sub.attrib.get("lang")
                result.add_name(ABCTypes.get_type("orgnametype",(type,)),
                                value)
            elif sub.tag == "realm":
                result.realm = value
            elif sub.tag == "address":
                if len(sub.attrib) <> 1:
                    raise ABCTypesError, "error in address: %s" % value
                type = sub.attrib.get("addresstype")
                addr_type = ABCTypes.get_type("addresstype",
                                              ("organization", type))
                result.add_address(addr_type, self._make_address(sub))
            elif sub.tag == "contactinfo":
                if len(sub.attrib) <> 1:
                    raise ABCTypesError, "error in contact: %s" % value
                if not sub.text:
                    continue
                type = sub.attrib.get("contacttype")
                result.add_contact(ABCTypes.get_type("contacttype",
                                                     ("organization", type,)),
                                   value)
            elif sub.tag == "ou" and result.ou is None:
                # Rather tricky. We have to represent the trailing OUs with
                # something. Returning an iterator seems viable.
                result.ou = ABCFactory.get('OUParser')(iter(element.getiterator("ou")))

        return result


class XMLOU2ObjectMixIn(XMLOU2Object):
    """A converter class that maps ElementTree's Element to DataOU."""

    def __init__(self, xmliter):
        """Constructs an iterator supplying DataPerson objects."""
        super(XMLOU2ObjectMixIn, self).__init__(xmliter)

    def next(self):
        """Return the next DataOU object. Returns a ABCTypesError
        exception if object has errors in types. These objects should be
        skipped.

        Consume the next XML-element describing an OU, and return a
        suitable representation (DataOU).
        """

        # This call with propagate StopIteration when all the (XML) elements
        # are exhausted.
        element = super(XMLOU2Object, self).next()
        result = DataOUMixin()
       
        # Iterate over *all* subelements
        for sub in element.getiterator():
            value = None
            if sub.text:
                value = sub.text.strip().encode("latin1")

            if sub.tag == "ouid":
                if len(sub.attrib) <> 1:
                    raise ABCTypesError, "error in ouid: %s" % value
                type = sub.attrib.get("ouidtype")
                ## FIXME: *very*, *very* ugly...
                if type == 'stedkode':
                    result.stedkodes.append(value)
                else:
                    result.add_id(ABCTypes.get_type("ouidtype",(type,)),
                              value)
            elif sub.tag == "ouname":
                if len(sub.attrib) <> 2:
                    raise ABCTypesError, "error in ouname: %s" % value
                type = sub.attrib.get("ounametype")
                # TODO: support lang
                lang = sub.attrib.get("lang")
                result.add_name(ABCTypes.get_type("ounametype",(type,)),
                                value)
            elif sub.tag == "parentid":
                if len(sub.attrib) <> 1:
                    raise ABCTypesError, "error in parentid: %s" % value
                type = sub.attrib.get("ouidtype")
                result.parent = (ABCTypes.get_type("ouidtype",(type,)),
                                 value)
            elif sub.tag == "replacedbyid":
                if len(sub.attrib) <> 1:
                    raise ABCTypesError, "error in replacedbyid: %s" % value
                type = sub.attrib.get("ouidtype")
                ## result.add_id(ABCTypes.get_type("ouidtype", (type,)), value)
                ## added by a mixin
                if value:
                    result.replacedby = value
            elif sub.tag == "address":
                if len(sub.attrib) <> 1:
                    raise ABCTypesError, "error in address: %s" % value
                type = sub.attrib.get("addresstype")
                addr_type = ABCTypes.get_type("addresstype",
                                              ("organization", type))
                result.add_address(addr_type, self._make_address(sub))
            elif sub.tag == "contactinfo":
                if len(sub.attrib) <> 1:
                    raise ABCTypesError, "error on contactinfo: %s" % value
                if not sub.text:
                    continue
                type = sub.attrib.get("contacttype")
                result.add_contact(ABCTypes.get_type("contacttype",
                                                     ("organization", type,)),
                                   value)
           
        # NB! This is crucial to save memory on XML elements
        element.clear()
        return result
    

class XMLPerson2ObjectMixIn(XMLPerson2Object):
    """A converter class that maps ElementTree's Element to DataPerson."""

    def __init__(self, xmliter):
        """Constructs an iterator supplying DataPerson objects."""

        super(XMLPerson2ObjectMixIn, self).__init__(xmliter)


    def next(self):
        """Return the next DataPerson object. Returns a ABCTypesError
        exception if object has errors in types. These objects should be
        skipped.

        Consume the next XML-element describing a person, and return a
        suitable representation (DataPerson).
        """

        # This call with propagate StopIteration when all the (XML) elements
        # are exhausted.
        element = super(XMLPerson2Object, self).next()
        result = DataPersonMixin()
        
        # Iterate over *all* subelements
        for sub in element.getiterator():
            value = None
            if sub.text:
                value = sub.text.strip().encode("latin1")
            if sub.tag == "personid":
                if len(sub.attrib) <> 1:
                    raise ABCTypesError, "error in personid: %s" % value
                type = sub.attrib.get("personidtype")
                if type == "fnr_closed":
                    result.fnr_closed.append(int(value))
                else:
                    result.add_id(ABCTypes.get_type("personidtype",(type,)),
                              value)
            elif sub.tag == "name":
                for t,v in self._make_person_name(sub):
                    result.add_name(t, v)
            elif sub.tag == "birthdate":
                # if len == 6 we asume ddmmyy
                if value == None:
                    result.birth_date = None
                else:
                    if len(value) == 6:
                        value = "19%s-%s-%s" % (value[4:6], value[2:4], value[0:2])
                    result.birth_date = self._make_mxdate(value)
                if not result.birth_date:
                    for k in result._ids.keys():
                        print k, result._ids[k]
                    print 'None'
            elif sub.tag == "gender":
                result.gender = value.lower()
            elif sub.tag == "address":
                if len(sub.attrib) <> 1:
                    raise ABCTypesError, "error in address: %s" % value
                type = sub.attrib.get("addresstype")
                addr_type = ABCTypes.get_type("addresstype",("person", type))
                result.add_address(addr_type, self._make_address(sub))
            elif sub.tag == "contactinfo":
                if len(sub.attrib) <> 1:
                    raise ABCTypesError, "error in contactinfo: %s" % value
                if not sub.text:
                    continue
                type = sub.attrib.get("contacttype")
                result.add_contact(ABCTypes.get_type("contacttype",
                                                     ("person", type,)),
                                   value)
            
            elif sub.tag == "reserv_publish":
                if value:
                    result.reserv_publish = value.lower()
        # NB! This is crucial to save memory on XML elements
        element.clear()
        return result

# arch-tag: fce4714a-6995-11da-9335-31e799a56356
