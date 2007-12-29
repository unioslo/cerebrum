# -*- coding: iso-8859-1 -*-
# Copyright 2005-2007 University of Oslo, Norway
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
This module implements an abstraction layer for various XML data sources.

Specifically, we build an API for dealing with data sources in terms of
suitable object abstractions rather than lower level primitives (such as
dictionaries representing XML-elements or sequences of db_rows). Details such
as date representations, external ids, etc. should be generalized as much as
possible.

A tentative sketch of the abstraction layer is located at:

<URL: http://folk.uio.no/runefro/tmp/imp/skisse.html>

We rely on the cElementTree/ElementTree library for parsing XML files:

<URL: http://effbot.org/zone/element-index.htm>


TODO:
-----
* Timing of cElementTree vs. other parsers (xml.sax + dict manipulation).
* Decision on sko-representation. I do not think a simple string would do,
  as a sko is often regarded as a tuple or as a dict. We need something more
  flexible.
* Fix the documentation and provide a few more examples.
"""

import copy
import os.path
import re
import sys
import time
import traceback
import types

from cElementTree import parse, iterparse, ElementTree
# from elementtree.ElementTree import parse, iterparse
from mx.DateTime import Date





#######################################################################
# Data abstraction for client code: Address, Employment, Person, etc.
#######################################################################

class DataAddress(object):
    """Class for storing address information.

    TBD: We should include some form for address validation.
    """

    ADDRESS_BESOK   = "besøk"
    ADDRESS_PRIVATE = "private"
    ADDRESS_POST    = "post"

    country2ziplength = {
        "": 4, "NO": 4, "DK": 4
        }

    def __init__(self, kind, street = (), zip = "", city = "", country = ""):
        self.kind = kind
        if isinstance(street, (list, tuple)):
            self.street = "\n".join(filter(None, map(str.strip, street)))
        else:
            self.street = street.strip()
        self.city = city.strip()
        # FIXME: match with something in cerebrum?
        self.country = country = country.strip()
        try:
            izip = int(zip)
            if izip == 0:
                self.zip = ""
            else:
                self.zip = "%0*d" % (self.country2ziplength[country], izip)
        except (ValueError, KeyError):
            self.zip = zip.strip()
        if self.country not in ("CA", "GB", "IT", "NL", "NO", "RU", "SE", "US"):
            # TBD: Log it with the logger framework?
            self.country = None
        # fi
    # end __init__


    def __str__(self):
        return "%s, %s, %s, %s" % (self.street, self.zip,
                                   self.city, self.country)
    # end __str__
# end DataAddress



class DataContact(object):

    CONTACT_PHONE      = "generic phone"
    CONTACT_FAX        = "fax"
    CONTACT_URL        = "url"
    CONTACT_EMAIL      = "e-mail"
    CONTACT_PRIVPHONE  = "private phone"
    CONTACT_MOBILE     = "cell phone"

    """Class for storing contact information (phone, e-mail, URL, etc.)"""

    def __init__(self, kind, value, priority):
        self.kind = kind
        assert self.kind in (self.CONTACT_PHONE, self.CONTACT_FAX,
                             self.CONTACT_URL, self.CONTACT_EMAIL,
                             self.CONTACT_PRIVPHONE, self.CONTACT_MOBILE)
        self.value = value
        self.priority = priority
    # end __init__


    def __str__(self):
        return "contact (%s): %s" % (self.kind, self.value)
    # end __str__
# end DataContact



class DataEmployment(object):
    """Class for representing employment information.

    TBD: Do we validate (the parts of) the information against Cerebrum?
    """

    HOVEDSTILLING = "hovedstilling"
    BISTILLING    = "bistilling"
    GJEST         = "gjest"
    BILAG         = "bilag"
    KATEGORI_OEVRIG = "tekadm-øvrig"
    KATEGORI_VITENSKAPLIG  = "vitenskaplig"

    def __init__(self, kind, percentage, code, title, start, end, place, category, leave=None):
        # TBD: Subclass?
        self.kind = kind
        assert self.kind in (self.HOVEDSTILLING, self.BISTILLING,
                             self.GJEST, self.BILAG)
        # It can be a floating point value.
        self.percentage = percentage
        self.code = code
        self.title = title
        # start/end are mx.DateTime objects (well, only the Date part is used)
        self.start = start
        self.end = end
        # Associated OU identified with (kind, value)-tuple.
        self.place = place
        # Kind of employment -- VIT/TEKADM-ØVR
        self.category = category
        # leave (should be a sequence of dict-like objects)
        if not leave:
            self.leave = list()
        else:
            self.leave = copy.deepcopy(leave)
    # end __init__

    def is_main(self):
        return self.kind == HRDataPerson.HOVEDSTILLING
    # end is_main

    def is_guest(self):
        return self.kind == self.GJEST

    def is_active(self, date = Date(*time.localtime()[:3])):
        # NB! None <= Date(...) == True
        return self.start <= date and ((not self.end) or
                                       (date <= self.end))
    # end is_active

    def has_leave(self, date = Date(*time.localtime()[:3])):
        for l in self.leave:
            if l['start_date'] <= date and (date <= l['end_date']):
                return True
        return False
    # end has_leave


    def __str__(self):
        return "(%s) Employment: %s%% %s [%s..%s @ %s]" % (self.kind,
                                                           self.percentage,
                                                           self.title,
                                                           self.start,
                                                           self.end,
                                                           self.place)
    # end __str__
# end DataEmployment


class DataName(object):
    """Class for representing name information in a data source.

    Typically this includes the string value itself and perhaps a language
    attribute.
    """

    def __init__(self, kind, value, lang=None):
        """Registers a new language.

        lang values are 2-digit ISO 639 codes as found in
        <http://www.w3.org/WAI/ER/IG/ert/iso639.htm>
        """

        self.kind = kind
        self.value = value
        self.language = lang
        if self.language:
            self.language = self.language.lower()
            # IVR 2007-07-14 FIXME: Yes, this is a hack. 
            if self.language == "ny":
                self.language = "nn"
            # IVR 2007-05-28 FIXME: This is perhaps the wrong place for such a
            # check.  We may want to (and should?) have these codes in
            # Cerebrum.
            if self.language not in ("en", "it", "nl", "no", "nb", "nn",
                                     "ru", "sv", "fr",):
                raise ValueError, "Unknown language code " + self.language
    # end __init__


    def __str__(self):
        if self.language:
            return str((self.kind, self.value, self.language))
        return str((self.kind, self.value))
# end DataName


class DataEntity(object):
    """Class for representing common traits of objects in a data source.

    Typically, a subclass of DataEntity will be a Person or an OU.
    """
    
    def __init__(self):
        self._external_ids = dict()
        self._names = dict()
        self._contacts = list()
        self._addresses = dict()
    # end __init__

    def add_id(self, kind, value):
        self.validate_id(kind, value)
        self._external_ids[kind] = value
    # end add_id

    def add_name(self, name):
        """Add a new name.

        We can have several names of the same kind. If this happens, they are
        all chained together under the kind key.
        """

        self.validate_name(name)
        kind = name.kind

        if kind in self._names:
            if isinstance(self._names[kind], types.ListType):
                self._names[kind].append(name)
            else:
                self._names[kind] = [self._names[kind], name]
            # fi
        else:
            self._names[kind] = name
        # fi
    # end add_name

    def add_contact(self, contact):
        self._contacts.append(contact)
    # end add_contact

    def add_address(self, address):
        if address:
            self._addresses[address.kind] = address
    # end add_address

    def iterids(self):
        return self._external_ids.iteritems()
    # end iterids

    def iternames(self):
        return self._names.iteritems()
    # end iternames

    def itercontacts(self):
        return iter(self._contacts)
    # end itercontacts

    def iteraddress(self):
        return self._addresses.iteritems()
    # end iteraddress

    def get_name(self, kind, default=None):
        tmp = self._names.get(kind, default)
        return tmp
    # end get_name

    def get_name_with_lang(self, kind, *priority_order):
        """Extract a name of given kind, respecting the given priority order.

        priority_order contains languages in the preferred order. If no
        language matches, we return None. NB! None is different from a name
        that is an empty string.
        """

        # Names without language come last
        max = len(priority_order)+1
        weights = { None : max, }
        i = 0
        for lang in priority_order:
            weights[lang.lower()] = i
            i += 1
        # od

        # If we have no name of this kind at all, just return None at once.
        names = self._names.get(kind, None)
        if names is None:
            return None
        # fi
        
        # it can be an atom or a list...
        if not isinstance(names, types.ListType):
            names = [names]
        # fi
        
        names = filter(lambda x: x.language in priority_order, names)
        names.sort(lambda x, y: cmp(weights[x.language],
                                    weights[y.language]))
        if names:
            return names[0].value
        else:
            return None
        # fi
    # end get_name_with_lang


    def get_contact(self, kind, default=list()):
        result = list()
        for contact in self.itercontacts():
            if contact.kind == kind:
                result.append(contact)
            # fi
        # od

        return result or default
    # end get_contact

    def get_id(self, kind, default=None):
        return self._external_ids.get(kind, default)
    # end get_id

    def get_address(self, kind, default=None):
        return self._addresses.get(kind, default)
    # end get_address

# end DataEntity    
    


class DataOU(DataEntity):
    """Class for representing OUs in a data source."""

    NO_SKO       = "sko"
    NO_NSD       = "nsdkode"

    NAME_ACRONYM = "acronym"
    NAME_SHORT   = "short"
    NAME_LONG    = "long"
    NAME_USAGE_AREA = "usage area"

    def __init__(self):
        super(DataOU, self).__init__()
        self.parent = None
        # Whether this OU can be published in electronic catalogues
        self.publishable = False
        self.start_date = None
        self.end_date = None
    # end __init__


    def validate_id(self, kind, value):
        assert kind in (self.NO_SKO, self.NO_NSD,)
    # end validate_id


    def validate_name(self, name):
        assert name.kind in (self.NAME_ACRONYM, self.NAME_SHORT, self.NAME_LONG)
    # end validate_name


    def __str__(self):
        return "DataOU (valid: %s-%s): %s\n%s\n%s" % (
            self.start_date, self.end_date,
            list(self.iterids()), list(self.iternames()),
            list(self.itercontacts()))
    # end __str__
# end DataOU



class DataPerson(DataEntity):
    """Class for representing people in a data source."""

    # TBD: Cerebrum constants?
    NAME_FIRST    = "FIRST"
    NAME_LAST     = "LAST"
    NAME_MIDDLE   = "MIDDLE"
    NAME_TITLE    = "personal title"
    NO_SSN        = "NO SSN"
    GENDER_MALE   = "M"
    GENDER_FEMALE = "F"
    GENDER_UNKNOWN = "X"
    

    def __init__(self):
        super(DataPerson, self).__init__()
    # end __init__


    def validate_id(self, kind, value):
        assert kind in (self.NO_SSN,)
    # end validate_id


    def validate_name(self, name):
        assert name.kind in (self.NAME_FIRST, self.NAME_LAST, self.NAME_MIDDLE,
                             self.NAME_TITLE)
    # end validate_name


    def __str__(self):
        ret = "DataPerson: %s\n" % list(self.iterids())
        for kind, name in self.iternames():
            ret += "%s: %s\n" % (kind, name.value)
        return ret
    # end __str__
# end DataPerson



class HRDataPerson(DataPerson):
    """Class for representing employees in a data source."""

    def __init__(self):
        super(HRDataPerson, self).__init__()

        self.gender = None
        self.birth_date = None
        self.employments = list()
        self.reserved = None
    # end __init__


    def add_employment(self, emp):
        self.employments.append(emp)
    # end add_employment


    # IVR 2007-03-06 FIXME: ugh! name consistency was not a top priority to
    # say the least :( There should be a "_" here.
    def iteremployment(self):
        return iter(self.employments)
    # end iteremployment


    def has_active_employments(self, timepoint = Date(*time.localtime()[:3])):
        """Decide whether this person has employments at a given timepoint."""

        for x in self.iteremployment():
            if ((x.kind in (x.HOVEDSTILLING, x.BISTILLING) and
                 x.is_active(timepoint)) or
                # IVR 2007-01-19 FIXME: This is a horrible, gruesome, vile,
                # ugly, repulsive and hairy pile of crud. It MUST DIE, once we
                # get rid of LT.
                (x.kind == x.GJEST and x.code == "POLS-ANSAT")):
                return True

        return False
    # end has_active_employments


    def __str__(self):
        spr = super(HRDataPerson, self).__str__()
        result = ("HRDataPerson: %s\n" 
                  "\tgender: %s\n"
                  "\tbirth: %s\n"
                  "\taddress: %s\n"
                  "\temployment: %s" % (spr, self.gender,
                                        self.birth_date,
                                        [str(x) for x in
                                         list(self.iteraddress())],
                                        [str(x) for x in
                                         list(self.iteremployment())]))
        return result
    # end __str__
# end HRDataPerson



class AbstractDataGetter(object):
    """
    An abstraction layer for information extraction from various authoritative
    systems.

    This class operates in terms of DataPerson, DataOU, DataGroup and the
    like. It relies exclusively on the information available through these
    interfaces.
    """

    def __init__(self, logger, fetchall = True):
        """Initialize the data source extractor.

        fetchall decides whether the data is fetched incrementally or is
        loaded entirely into memory (cf. db_row).
        """

        self.logger = logger
        self.fetch(fetchall)
    # end __init__


    def fetch(self, fetchall = True):
        """Connect to data source and fetch data."""
        raise NotImplementedError("fetch not implemented")
    # end fetch
    
    
    def iter_person(self):
        """Give an iterator over person objects in the data source."""
        raise NotImplementedError("iter_person not implemented")
    # end iter_person

            
    def iter_ou(self):
        """Give an iterator over OU objects in the data source."""
        raise NotImplementedError("iter_ou not implemented")
    # end iter_ou
# end AbstractDataGetter



class XMLDataGetter(AbstractDataGetter):
    """This class provides abstractions to operate on XML files."""

    def __init__(self, filename, logger, fetchall = True):
        self._filename = filename
        self._data_source = None

        super(XMLDataGetter, self).__init__(logger, fetchall)
    # end __init__


    def _make_iterator(self, element, klass):
        """Create an iterator over XML elements.

        Creates an iterator over XML elements 'element' that returns instances
        of class klass.
        """
        
        if self._data_source:
            it = self._data_source.getiterator(element)
        else:
            it = XMLEntityIterator(self._filename, element)

        return klass(iter(it), self.logger)
    # end _make_iterator


    def fetch(self, fetchall = True):
        """Parse the XML file and convert it to HRDataPerson objects."""
        if fetchall:
            # Load the entire tree in memory. NB! Use with caution on large
            # files. The memory footprint is around 5x the file size.
            # 
            # If the file is too big, we'd just created iterators for the
            # XML elements on the fly. This provides us with an iterator
            # whose next() is invoked after each 'end element' event. NB!
            # Remember that the elements *MUST* be explicitely released if
            # they are no longer needed (or they'll end up cached in memory;
            # something we are trying to avoid here).
            self._data_source = parse(self._filename)
    # end fetch
# end XMLDataGetter



class XMLEntity2Object(object):
    """A small helper for common XML -> Data*-class conversions.

    The subclasses of this class have to implement one method, essentially:
    next_object(element). This method should create an object (an instance of
    DataEntity) that is the representation of an XML subtree. If for some
    reason such an object cannot be created, None must be returned.
    """

    def __init__(self, xmliter, logger):
        """Constructs an iterator supplying DataEntity objects.

        xmliter is the the underlying ElementTree iterator (here we do not
        care if it is in-memory or on file).
        """

        self._xmliter = iter(xmliter)
        self.logger = logger
    # end __init__


    def next(self):
        """Return next object constructed from a suitable XML element

        Reads the 'next' element and returns an object constructed out of it,
        if at all possible. The object construction is dispatched to
        subclasses (via next_object). If the object construction fails,
        next_object should return None.

        This method would consume subsequent XML elements/subtrees until a
        suitable object can be constructed or we run out of XML elements. In
        the latter case StopIteration is thrown (as per iterator protocol).

        IVR 2007-12-25 TBD: releasing the memory occupied by subtrees is quite
        helpful, but very ugly in this code. This should be implemented more
        elegantly.
        """
        
        while 1:
            try:
                # Fetch the next XML subtree...
                element = self._xmliter.next()
                # ... and dispatch to subclass to create an object
                obj = self.next_object(element)

                # free the memory in the ElementTree framework.
                element.clear()

                # IVR 2007-12-28 TBD: Do we want some generic 'no object
                # created' error message here? The problem with such a message
                # is that it is difficult to ignore a separate generic error
                # line in the logs. Typically, when obj is None,
                # next_element() would have made (or at least, it should have)
                # some sort of error message which explains far better what
                # went wrong, thus making a generic message here somewhat
                # moot.
                if obj is not None:
                    return obj
            except StopIteration:
                raise
            except:
                # If *any* sort of exception occurs, log this, and continue
                # with the parsing. We cannot afford one defective entry to
                # break down the entire data import run.
                if self.logger:
                    self.logger.warn("%s occurred while processing "
                                     "XML element %s. Skipping it.",
                                     self._format_exc_context(sys.exc_info()),
                                     element.tag)
                element.clear()
    # end next


    def __iter__(self):
        return self
    # end __iter__


    def _make_mxdate(self, text, format = "%Y%m%d"):
        """Helper method to convert strings to dates.

        @param text:
          A string containing formatted date. The string may be empty.
        @type text: basestring

        @param format:
          A format string (cf. strptime) describing the datum in text.
        @type format: basestring

        @return
        @rtype: mx.DateTime.Date

        """
        if not text:
            return None
        
        year, month, day = time.strptime(text, format)[:3]
        return Date(year, month, day)
    # end _make_mxdate


    def exception_wrapper(functor, exc_list=(), return_on_error=None):
        """Helper method for discarding exceptions easier.

        We can wrap around a call to a method, so that a certain exception (or
        a sequence thereof) would result in in returning a specific
        value. A typical use case would be:

            >>> class A(XMLEntity2Object):
            ...    def foo(self, ...):
            ...        # do something
            ...    # end foo
            ...    foo = A.exception_wrapper(foo, (AttributeError, ValueError),
            ...                              (None, None))

        ... which would result in a warn message in the logs, if foo() raises
        AttributeError or ValueError. foo() above can take rest and keyword
        arguments.

        @param functor:
          A callable object which we want to wrap around.
        @type functor:
          A function, a method (bound or unbound) or an object implementing
          the __call__ special method.

        @param exc_list
          A sequence of exception classes to intercept. An empty list would
          mean all exceptions are let through. 'object' would mean that
          everything is intercepted.
        @type exc_list: a tuple, a list, a set or another class implementing
          the __iter__ special method.

        @return: A function invoking functor when called. rest and keyword
        arguments are supported.
        @rtype: function.

        IVR 2007-11-22 TBD: Maybe this belongs in Utils.py somewhere?
        """

        def wrapper(*rest, **kw_args):
            try:
                return functor(*rest, **kw_args)
            except tuple(exc_list):
                if self.logger:
                    self.logger.warn(
                        XMLEntity2Object._format_exc_context(sys.exc_info()))
                return return_on_error
            # end wrapper

        return wrapper
    # end exception_wrapper
    exception_wrapper = staticmethod(exception_wrapper)


    def _format_exc_context((etype, evalue, etraceback)):
        """Small helper for printing exception context.

        This static method helps format an exception traceback.
        """
        tmp = traceback.extract_tb(etraceback)
        filename, line, funcname, text = tmp[-1]
        filename = os.path.basename(filename)
        return ("Exception %s while parsing XML (in context %s): %s" %
                (etype,
                 "%s/%s() @line %s" % (filename, funcname, line),
                 evalue))
    # end _format_exc_context
    _format_exc_context = staticmethod(_format_exc_context)


    def format_xml_element(self, element):
        """Returned a 'serialized' version of an XML element.

        Occasionally it is useful to know which XML subtree caused the
        problem. This helper method does just that. StringIO is probably not
        particularily fast, so use sparingly.

        @type element: Element instance.
        @param subtree:
          An Element object (from ElementTree), the string representation of
          which is returned.

        @rtype: basestring
        @return:
          String representation of L{subtree}. This is the XML used to
          construct subtree initially (up to varying whitespace, perhaps).
        """

        import cStringIO
        stream = cStringIO.StringIO()
        ElementTree(element).write(stream)
        return stream.getvalue()
    # end format_xml_element
# end XMLEntity2Object


    
class XMLEntityIterator(object):
    """Iterate over an XML file and return complete elements of a given kind.

    Iterative parsing in ElementTree is based on (event, element) pairs. For
    dealing with people, OUs and the like, we need look at ('end',<ElementTree
    'something'>) only, where 'something' represents the entity we are
    interested in. In a sense, this class iterates over XML subtrees. 
    """

    def __init__(self, filename, element):
        # iterparse itself is not necessarily an iterator. Therefore iter()
        self.it = iter(iterparse(filename, ("start", "end")))
        self.element_name = element

        # Keep track of the root element (to prevent element caching)
        junk, self._root = self.it.next()
    # end __init__
        

    def next(self):
        """Return next specified element, ignoring all else.

        This method operates on cElementTree's trees. The specified element is
        returned as such a tree. The intention is for the subclasses to call
        this method, get a tree back, remap the tree to
        DataAddress/DataPerson/and so forth, and return a suitable
        Data*-object.
        """
        
        # Each time next is called, we drop whatever is dangling under root.
        # It might be problematic if there is *a lot* of elements between two
        # consecutive self.element_name elements, as all of them are kept in
        # memory (it's like that by design).
        self._root.clear()
        
        for event, element in self.it:
            if event == "end" and element.tag == self.element_name:
                return element

            # See the explanation above.
            self._root.clear()

        raise StopIteration
    # end next
                

    def __iter__(self):
        return self
    # end __iter__
# end XMLEntityIterator
