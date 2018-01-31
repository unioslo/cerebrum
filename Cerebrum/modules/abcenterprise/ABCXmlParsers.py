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
import sys
import time
from mx.DateTime import Date

import abcconf

from Cerebrum.modules.abcenterprise.ABCUtils import ABCTypes
from Cerebrum.modules.abcenterprise.ABCUtils import ABCTypesError
from Cerebrum.modules.abcenterprise.ABCUtils import ABCFactory
from Cerebrum.modules.abcenterprise.ABCDataObjects import DataPerson
from Cerebrum.modules.abcenterprise.ABCDataObjects import DataOU
from Cerebrum.modules.abcenterprise.ABCDataObjects import DataGroup
from Cerebrum.modules.abcenterprise.ABCDataObjects import DataRelation
from Cerebrum.modules.abcenterprise.ABCDataObjects import DataAddress

class XMLEntityIterator:
    """Iterate over an XML file and return complete elements of a given kind.

    Iterative parsing in ElementTree is based on (event, element) pairs. For
    dealing with people, OUs and the like, we need look at ('end',<ElementTree
    'something'>) only, where 'something' represents the entity we are
    interested in.
    """

    def __init__(self, filename, element):
        # Load cElementTree or ElementTree depending on configuration
        if abcconf.CLASS_XMLPARSER == 'ElementTree':
            from xml.etree.ElementTree import parse, iterparse
        elif abcconf.CLASS_XMLPARSER == 'cElementTree':
            from xml.etree.cElementTree import parse, iterparse
        else:
            print abcconf.CLASS_XMLPARSER
            print """
CLASS_XMLPARSER in abcconf only supports 'ElementTree' and cElementTree'."""
            sys.exit(1)

        self.it = iter(iterparse(filename, ("start", "end")))
        self.element_name = element

        # Keep track of the root element (to prevent element caching)
        junk, self._root = self.it.next()


    def next(self):
        """Return next specified element, ignoring all else."""

        # Each time next is called, we drop whatever is dangling under
        # root. It might be problematic if there is *a lot* of elements
        # between two consecutive self.element_name elements.
        self._root.clear()

        for event, element in self.it:
            if event == "end" and element.tag == self.element_name:
                return element
        raise StopIteration


    def __iter__(self):
        return self


class XMLPropertiesParser(object):

    def __init__(self, xmliter):
        """Constructs an iterator supplying settings."""
        self._xmliter = xmliter


    def __iter__(self):
        return self

    def _check_type(self, type, args):
        # Should throw exception if anything is fishy
        ABCTypes.get_type(type, args)

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

                    # Get the "strange" types
                    elif n.tag in ("addresstype", "contacttype", "relationtype", "tagtype"):
                        for t, v in (("addresstype", 1),
                                     ("contacttype", 1),
                                     ("relationtype", 2),
                                     ("tagtype", 1)):
                            if not n.tag == t:
                                continue
                            if len(n.attrib) != v:
                                raise ABCTypesError, "wrong number of attributes"
                            attr = None
                            subj = n.attrib.get("subject")
                            if v > 1:
                                obj =  n.attrib.get("object")
                                attr = (subj, obj, value)
                            else:
                                attr = (subj, value)
                            self._check_type(t, attr)
                    elif n.tag != "types":
                        raise ABCTypesError, "got unknown type: %s" % n.tag
        # NB! This is crucial to save memory on XML elements
        element.clear()
        return (datasource, target, timestamp)


class XMLEntity2Object(object):

    def __init__(self, xmliter):
        """Constructs an iterator supplying DataEntity objects.

        xmliter is the the underlying ElementTree iterator (here we do not
        care if it is in-memory or on file).
        """
        self._xmliter = xmliter


    def next(self):
        tmp = self._xmliter.next()
        return tmp


    def _make_mxdate(self, text, format = "%Y-%m-%d"):
        try:
            year, month, day = time.strptime(text, format)[:3]
        except ValueError:
            return None
        return Date(year, month, day)


    def __iter__(self):
        return self


    def _make_address(self, addr_element):
        """Make a list of tuples out of an <adresse>."""
        assert addr_element.tag == "address"
        result = DataAddress()
        for sub in addr_element.getiterator():
            if not sub.text:
                continue
            value = sub.text.strip().encode("latin1")
            for tag in ("pobox", "street", "postcode", "city", "country"):
                if not tag == sub.tag:
                    continue
                setattr(result, tag, value)
        return result


class XMLOrg2Object(XMLEntity2Object):
    """A converter class that maps ElementTree's Element to DataOU.
    An Organization is represented as an OU."""

    def __init__(self, xmliter):
        """Constructs an iterator supplying DataPerson objects."""

        super(XMLOrg2Object, self).__init__(xmliter)

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
        result = DataOU()

        # Iterate over *all* subelements
        for sub in element:
            value = None
            if sub.text:
                value = sub.text.strip().encode("latin1")
            if sub.tag == "orgid":
                if len(sub.attrib) != 1:
                    raise ABCTypesError, "wrong number of arguments: %s" % value
                type = sub.attrib.get("orgidtype")
                result.add_id(ABCTypes.get_type("orgidtype",(type,)),
                              value)
            elif sub.tag == "orgname":
                if len(sub.attrib) != 2:
                    raise ABCTypesError, "not 2 attributes: %s" % value
                type = sub.attrib.get("orgnametype")
                # TODO: support lang
                lang = sub.attrib.get("lang")
                result.add_name(ABCTypes.get_type("orgnametype",(type,)),
                                value)
            elif sub.tag == "realm":
                result.realm = value
            elif sub.tag == "address":
                if len(sub.attrib) != 1:
                    raise ABCTypesError, "error in address: %s" % value
                type = sub.attrib.get("addresstype")
                addr_type = ABCTypes.get_type("addresstype",
                                              ("organization", type))
                result.add_address(addr_type, self._make_address(sub))
            elif sub.tag == "contactinfo":
                if len(sub.attrib) != 1:
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


class XMLOU2Object(XMLEntity2Object):
    """A converter class that maps ElementTree's Element to DataOU."""

    def __init__(self, xmliter):
        """Constructs an iterator supplying DataPerson objects."""

        super(XMLOU2Object, self).__init__(xmliter)

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
        result = DataOU()

        # Iterate over *all* subelements
        for sub in element.getiterator():
            value = None
            if sub.text:
                value = sub.text.strip().encode("latin1")

            if sub.tag == "ouid":
                if len(sub.attrib) != 1:
                    raise ABCTypesError, "error in ouid: %s" % value
                type = sub.attrib.get("ouidtype")
                result.add_id(ABCTypes.get_type("ouidtype",(type,)),
                              value)
            elif sub.tag == "tag":
                if len(sub.attrib) != 1:
                    raise ABCTypesError, "error in tag: %s" % value
                type = sub.attrib.get("tagtype")
                result.add_tag(ABCTypes.get_type("tagtype",("ou", type)),
                               value)
            elif sub.tag == "ouname":
                if len(sub.attrib) != 2:
                    raise ABCTypesError, "error in ouname: %s" % value
                type = sub.attrib.get("ounametype")
                # TODO: support lang
                lang = sub.attrib.get("lang")
                result.add_name(ABCTypes.get_type("ounametype",(type,)),
                                value)
            elif sub.tag == "parentid":
                if len(sub.attrib) != 1:
                    raise ABCTypesError, "error in parentid: %s" % value
                type = sub.attrib.get("ouidtype")
                result.parent = (ABCTypes.get_type("ouidtype",(type,)),
                                 value)
            elif sub.tag == "address":
                if len(sub.attrib) != 1:
                    raise ABCTypesError, "error in address: %s" % value
                type = sub.attrib.get("addresstype")
                addr_type = ABCTypes.get_type("addresstype",
                                              ("ou", type))
                result.add_address(addr_type, self._make_address(sub))
            elif sub.tag == "contactinfo":
                if len(sub.attrib) != 1:
                    raise ABCTypesError, "error on contactinfo: %s" % value
                if not sub.text:
                    continue
                type = sub.attrib.get("contacttype")
                result.add_contact(ABCTypes.get_type("contacttype",
                                                     ("ou", type,)),
                                   value)

        # NB! This is crucial to save memory on XML elements
        element.clear()
        return result


class XMLPerson2Object(XMLEntity2Object):
    """A converter class that maps ElementTree's Element to DataPerson."""

    def __init__(self, xmliter):
        """Constructs an iterator supplying DataPerson objects."""

        super(XMLPerson2Object, self).__init__(xmliter)


    def _make_person_name(self, name_element):
        """Make a list out of <name>. Names are type+value in
        Cerebrum."""

        result = []
        for sub in name_element.getiterator():
            if not sub.text:
                continue
            value = sub.text.strip().encode("latin1")
            for tag in ("fn", "sort", "nickname"):
                if not tag == sub.tag:
                    continue
                if value:
                    result.append((ABCTypes.get_name_type(tag), value))
            if sub.tag == "n":
                for n in sub.getiterator():
                    if not n.text:
                        continue
                    value = n.text.strip().encode("latin1")
                    for tag in ("family", "given", "other", "prefix", "suffix"):
                        if not tag == n.tag:
                            continue
                        if value:
                            result.append((ABCTypes.get_name_type(tag), value))
                        if n.tag in ("partname",):
                            if len(n.attrib) != 1:
                                raise ABCTypesError, "error in partname: %s" % value
                            type = ABCTypes.get_type("partname",
                                                     (n.attrib.get("partnametype"),))
                            if value:
                                result.append((type, value))
        return result


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
        result = DataPerson()

        # Iterate over *all* subelements
        for sub in element.getiterator():
            value = None
            if sub.text:
                value = sub.text.strip().encode("latin1")

            if sub.tag == "personid":
                if len(sub.attrib) != 1:
                    raise ABCTypesError, "error in personid: %s" % value
                type = sub.attrib.get("personidtype")
                result.add_id(ABCTypes.get_type("personidtype",(type,)),
                              value)
            elif sub.tag == "tag":
                if len(sub.attrib) != 1:
                    raise ABCTypesError, "error in tag: %s" % value
                type = sub.attrib.get("tagtype")
                result.add_tag(ABCTypes.get_type("tagtype",("person", type)),
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
            elif sub.tag == "gender":
                result.gender = value
            elif sub.tag == "address":
                if len(sub.attrib) != 1:
                    raise ABCTypesError, "error in address: %s" % value
                type = sub.attrib.get("addresstype")
                addr_type = ABCTypes.get_type("addresstype",("person", type))
                result.add_address(addr_type, self._make_address(sub))
            elif sub.tag == "contactinfo":
                if len(sub.attrib) != 1:
                    raise ABCTypesError, "error in contactinfo: %s" % value
                if not sub.text:
                    continue
                type = sub.attrib.get("contacttype")
                result.add_contact(ABCTypes.get_type("contacttype",
                                                     ("person", type,)),
                                   value)


        # NB! This is crucial to save memory on XML elements
        element.clear()
        return result


class XMLGroup2Object(XMLEntity2Object):
    """A converter class that maps ElementTree's Element to DataGroup."""

    def __init__(self, xmliter):
        """Constructs an iterator supplying DataGroup objects."""

        super(XMLGroup2Object, self).__init__(xmliter)

    def next(self):
        """Return the next DataGroup object. Returns a ABCTypesError
        exception if object has errors in types. These objects should be
        skipped.

        Consume the next XML-element describing an OU, and return a
        suitable representation (DataGroup).
        """

        # This call with propagate StopIteration when all the (XML) elements
        # are exhausted.
        element = super(XMLGroup2Object, self).next()
        result = DataGroup()

        # Iterate over *all* subelements
        for sub in element.getiterator():
            value = None
            if sub.text:
                value = sub.text.strip().encode("latin1")

            if sub.tag == "groupid":
                if len(sub.attrib) != 1:
                    raise ABCTypesError, "error in groupid: %s" % value
                type = sub.attrib.get("groupidtype")
                result.add_id(ABCTypes.get_type("groupidtype",(type,)),
                              value)
            elif sub.tag == "tag":
                if len(sub.attrib) != 1:
                    raise ABCTypesError, "error in tag: %s" % value
                type = sub.attrib.get("tagtype")
                result.add_tag(ABCTypes.get_type("tagtype",("group", type)),
                               value)
            elif sub.tag == "description":
                result.desc = value

        # NB! This is crucial to save memory on XML elements
        element.clear()
        return result


class XMLRelation2Object(XMLEntity2Object):
    """A converter class that maps ElementTree's Element to DataRelation."""

    def __init__(self, xmliter):
        """Constructs an iterator supplying DataRelation objects."""

        super(XMLRelation2Object, self).__init__(xmliter)

    def _get_subvalues(self, iter):
        value = None
        result = []
        for s in iter:
            if s.text:
                value = s.text.strip().encode("latin1")
            if s.tag == "personid":
                if len(s.attrib) != 1:
                    raise ABCTypesError, "error in personid: %s" % value
                type = s.attrib.get("personidtype")
                result.append(("person", ABCTypes.get_type("personidtype",
                                                 (type,)),
                               value))
            elif s.tag == "groupid":
                if len(s.attrib) != 1:
                    raise ABCTypesError, "error in groupid: %s" % value
                type = s.attrib.get("groupidtype")
                result.append(("group", ABCTypes.get_type("groupidtype",
                                                          (type,)),
                               value))
            elif s.tag == "org":
                org = ou = None
                for o in s.getiterator():
                    if o.text:
                        value = o.text.strip().encode("latin1")
                    if o.tag == "orgid":
                        if len(o.attrib) != 1:
                            raise ABCTypesError, "error in org: %s" % value
                        type = o.attrib.get("orgidtype")
                        org = (ABCTypes.get_type("orgidtype",
                                                 (type,)),
                               value)
                    elif o.tag == "ouid":
                        if len(o.attrib) != 1:
                            raise ABCTypesError, "error in ouid: %s" % value
                        type = o.attrib.get("ouidtype")
                        ou = (ABCTypes.get_type("ouidtype",
                                                (type,)),
                              value)
                # Org is required
                if not org:
                    # raise ABCTypesError, "no org"
                    # TODO: enable again.
                    pass
                if org and ou:
                    result.append(("org", org, ou))
                elif org:
                    result.append(("org", org))
                else:
                    result.append(("ou", ou))
        return result


    def next(self):
        """Return the next DataRelation object. Returns a ABCTypesError
        exception if object has errors in types. These objects should be
        skipped.

        Consume the next XML-element describing an OU, and return a
        suitable representation (DataRelation).
        """

        # This call with propagate StopIteration when all the (XML) elements
        # are exhausted.
        element = super(XMLRelation2Object, self).next()
        result = DataRelation()

        # Iterate over *all* subelements
        for sub in element.getiterator():
            if not result.type:
                result.type = sub.attrib.get("relationtype")

            if sub.tag == "subject":
                res = self._get_subvalues(sub.getiterator())
                if (not isinstance(res, list)) or len(res) != 1:
                    raise ABCTypesError, "res is '%s'" % res
                result.subject = res
            elif sub.tag == "object":
                res = self._get_subvalues(sub.getiterator())
                if not isinstance(res, list):
                    raise ABCTypesError, "object is '%s' not a list" % res
                result.object = res

        # NB! This is crucial to save memory on XML elements
        element.clear()
        return result

