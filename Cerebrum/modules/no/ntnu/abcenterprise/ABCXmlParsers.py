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

from Cerebrum.modules.no.ntnu.abcenterprise.ABCUtils import ABCTypesExt
from Cerebrum.modules.abcenterprise.ABCUtils import ABCTypesError
from Cerebrum.modules.abcenterprise.ABCUtils import ABCFactory
from Cerebrum.modules.abcenterprise.ABCDataObjects import DataGroup
from Cerebrum.modules.abcenterprise.ABCDataObjects import DataRelation
from Cerebrum.modules.abcenterprise.ABCDataObjects import DataAddress
from Cerebrum.modules.abcenterprise.ABCXmlParsers import XMLOrg2Object
from Cerebrum.modules.abcenterprise.ABCXmlParsers import XMLOU2Object
from Cerebrum.modules.abcenterprise.ABCXmlParsers import XMLPerson2Object
from Cerebrum.modules.abcenterprise.ABCXmlParsers import XMLPropertiesParser


from Cerebrum.modules.no.ntnu.abcenterprise.ABCDataObjectsExt import DataPersonExt
from Cerebrum.modules.no.ntnu.abcenterprise.ABCDataObjectsExt import DataOUExt
from Cerebrum.Utils import Factory

class XMLPropertiesParserExt(XMLPropertiesParser):

    ## def __init__(self, xmliter):
    ##     """Constructs an iterator supplying settings."""
    ##     self._xmliter = xmliter


    ## def __iter__(self):
    ##     return self

    def _check_type(self, type, args):
        if not ABCTypesExt.get_type(type, args):
            #TODO: cleanup
            raise ABCTypesError, "wrong type and/or argument: '%s' '%s'" % (type, args)

    def next(self):
        """ """
        # This call with propagate StopIteration when all the (XML) elements
        # are exhausted.
        # Iterate over *all* subelements
        element = self._xmliter.next()
        datasource = target = timestamp = ""

        for sub in element.getiterator():
            value = None
            if sub.text:
                value = sub.text.strip().encode("latin1")

            if sub.tag == "datasource":
                datasource = value
            elif sub.tag == "target":
                target = value
            elif sub.tag == "timestamp":
                timestamp = value
            elif sub.tag == "types":
                for n in sub.getiterator():
                    if not n.text:
                        continue
                    value = n.text.strip().encode("latin1")
                    if n.tag in ("orgidtype",):
                        self._check_type("orgidtype", (value,))
                    elif n.tag in ("orgnametype",):
                        self._check_type("orgnametype", (value,))
                    elif n.tag in ("ouidtype",):
                        self._check_type("ouidtype", (value,))
                    elif n.tag in ("ounametype",):
                        self._check_type("ounametype", (value,))
                    elif n.tag in ("personidtype",):
                        self._check_type("personidtype", (value,))
                    elif n.tag in ("partnametype",):
                        self._check_type("partnametype", (value,))
                    elif n.tag in ("groupidtype",):
                        self._check_type("groupidtype", (value,))
                    elif n.tag in ("printplacetype"):
                        self._check_type("printplacetype", (value,))
                    elif n.tag in ("keycardtype"):
                        self._check_type("keycardtype",(value,))

                    # Get the "strange" types
                    elif n.tag in ("addresstype", "contacttype", "relationtype", "tagtype", ):
                        for t, v in (("addresstype", 1),
                                     ("contacttype", 1),
                                     ("relationtype", 2),
                                     ("tagtype", 1)):
                            if not n.tag == t:
                                continue
                            if len(n.attrib) <> v:
                                raise ABCTypesError, "wrong number of attributes"
                            attr = None
                            subj = n.attrib.get("subject")
                            if v > 1:
                                obj =  n.attrib.get("object")
                                attr = (subj, obj, value)
                            else:
                                attr = (subj, value)
                            self._check_type(t, attr)
                    elif n.tag <> "types":
                        raise ABCTypesError, "got unknown type: %s" % n.tag
        # NB! This is crucial to save memory on XML elements
        element.clear()
        return (datasource, target, timestamp)
                           
class XMLOrg2ObjectExt(XMLOrg2Object):
    """A converter class that maps ElementTree's Element to DataOU.
    An Organization is represented as an OU."""

    def __init__(self, xmliter):
        """Constructs an iterator supplying DataPerson objects."""

        super(XMLOrg2ObjectExt, self).__init__(xmliter)

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
        result = DataOUExt()
        
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
                    result.add_id(ABCTypesExt.get_type("orgidtype",(type,)),
                              value)
            elif sub.tag == 'business_category':
                pass
            elif sub.tag == 'ou_level':
                pass
            elif sub.tag == "orgname":
                if len(sub.attrib) <> 2:
                    raise ABCTypesError, "not 2 attributes: %s" % value
                type = sub.attrib.get("orgnametype")
                # TODO: support lang
                lang = sub.attrib.get("lang")
                result.add_name(ABCTypesExt.get_type("orgnametype",(type,)),
                                value)
            elif sub.tag == "realm":
                result.realm = value
            elif sub.tag == "address":
                if len(sub.attrib) <> 1:
                    raise ABCTypesError, "error in address: %s" % value
                type = sub.attrib.get("addresstype")
                addr_type = ABCTypesExt.get_type("addresstype",
                                              ("organization", type))
                result.add_address(addr_type, self._make_address(sub))
            elif sub.tag == "contactinfo":
                if len(sub.attrib) <> 1:
                    raise ABCTypesError, "error in contact: %s" % value
                if not sub.text:
                    continue
                type = sub.attrib.get("contacttype")
                result.add_contact(ABCTypesExt.get_type("contacttype",
                                                     ("organization", type,)),
                                   value)
            elif sub.tag == "ou" and result.ou is None:
                # Rather tricky. We have to represent the trailing OUs with
                # something. Returning an iterator seems viable.
                result.ou = ABCFactory.get('OUParser')(iter(element.getiterator("ou")))

        return result


class XMLOU2ObjectExt(XMLOU2Object):
    """A converter class that maps ElementTree's Element to DataOU."""

    def __init__(self, xmliter):
        """Constructs an iterator supplying DataPerson objects."""
        super(XMLOU2ObjectExt, self).__init__(xmliter)

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
        result = DataOUExt()
       
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
                    result.add_id(ABCTypesExt.get_type("ouidtype",(type,)),
                              value)
            elif sub.tag == 'business_category':
                pass
            elif sub.tag == 'ou_level':
                pass
            elif sub.tag == "ouname":
                if len(sub.attrib) <> 2:
                    raise ABCTypesError, "error in ouname: %s" % value
                type = sub.attrib.get("ounametype")
                # TODO: support lang
                lang = sub.attrib.get("lang")
                result.add_name(ABCTypesExt.get_type("ounametype",(type,)),
                                value)
            elif sub.tag == "parentid":
                if len(sub.attrib) <> 1:
                    raise ABCTypesError, "error in parentid: %s" % value
                type = sub.attrib.get("ouidtype")
                result.parent = (ABCTypesExt.get_type("ouidtype",(type,)),
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
                addr_type = ABCTypesExt.get_type("addresstype",
                                              ("organization", type))
                result.add_address(addr_type, self._make_address(sub))
            elif sub.tag == "contactinfo":
                if len(sub.attrib) <> 1:
                    raise ABCTypesError, "error on contactinfo: %s" % value
                if not sub.text:
                    continue
                type = sub.attrib.get("contacttype")
                result.add_contact(ABCTypesExt.get_type("contacttype",
                                                     ("organization", type,)),
                                   value)
           
        # NB! This is crucial to save memory on XML elements
        element.clear()
        return result
    

class XMLPerson2ObjectExt(XMLPerson2Object):
    """A converter class that maps ElementTree's Element to DataPerson."""

    def __init__(self, xmliter):
        """Constructs an iterator supplying DataPerson objects."""

        super(XMLPerson2ObjectExt, self).__init__(xmliter)
        self.logger = Factory.get_logger("cronjob")


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
        result = DataPersonExt()
        
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
                    result.fnr_closed.append(value)
                else:
                    result.add_id(ABCTypesExt.get_type("personidtype",(type,)),
                              value)
            elif sub.tag == "keycardid":
                # Ignoring keycards until we have fixed the issue with
                # duplicate keycards.
                # TODO: Fix and stuff
                continue
                if len(sub.attrib) <> 1:
                    raise ABCTypesError, "error in keycardid: %s" % value
                type = sub.attrib.get("keycardtype")
                ## we do not want the import to stop for the
                ## person,- just log a nice message
                key = ABCTypesExt.get_type("keycardtype",(type,))
                ret = result._ids.get(key)
                if ret:
                    msg = ''
                    ## get hold of all the ids that can help
                    ## to identitfy the person.
                    for k in result._ids.keys():
                        msg = msg + '%s = %s, ' % (k, result._ids.get(k))
                    msg = msg + ' conflicting %s; new value = %s.' % (key, value)
                    self.logger.warn(msg)
                result.add_id(ABCTypesExt.get_type("keycardtype",(type,)),
                              value)
            ## ignoring this one.
            ## primary affiliation is printplace.
            ## may change later...
            elif sub.tag == "printplace":
                pass
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
                addr_type = ABCTypesExt.get_type("addresstype",("person", type))
                result.add_address(addr_type, self._make_address(sub))
            elif sub.tag == "contactinfo":
                if len(sub.attrib) <> 1:
                    raise ABCTypesError, "error in contactinfo: %s" % value
                if not sub.text:
                    continue
                type = sub.attrib.get("contacttype")
                result.add_contact(ABCTypesExt.get_type("contacttype",
                                                     ("person", type,)),
                                   value)
            
            elif sub.tag == "reserv_publish":
                if value:
                    result.reserv_publish = value.lower()
        # NB! This is crucial to save memory on XML elements
        element.clear()
        return result

# arch-tag: fce4714a-6995-11da-9335-31e799a56356
