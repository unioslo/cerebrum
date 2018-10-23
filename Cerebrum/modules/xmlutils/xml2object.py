# -*- coding: utf-8 -*-
# Copyright 2005-2018 University of Oslo, Norway
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
from __future__ import unicode_literals

import copy
import time

from xml.etree.cElementTree import parse, iterparse, ElementTree
from six import text_type

from mx.DateTime import Date, DateTimeDelta

import cereconf
from Cerebrum import Utils


def get_xml_file_encoding(file_name):
    """
    A relatively naive way of determining the encoding used in a xml-file.
    """
    with open(file_name, 'r') as xml_file:
        encoding = None
        while encoding is None:
            line = xml_file.readline()
            if line.startswith('<?xml'):
                if 'encoding=' in line:
                    encoding = line.split('encoding="')[1].split('"')[0]
                    return encoding
                else:
                    raise Exception('No encoding specified in {}'
                                    ''.format(file_name))
            elif line.startswith('<') or line == '':
                raise Exception('No encoding specified in {}'
                                ''.format(file_name))


def ensure_unicode(text, encoding):
    if not isinstance(text, basestring):
        raise Exception('Not a string: {}'.format(text))
    if isinstance(text, str):
        return text.decode(encoding)
    return text


#######################################################################
# Data abstraction for client code: Address, Employment, Person, etc.
#######################################################################

class DataAddress(object):
    """Class for storing address information.

    TBD: We should include some form for address validation.
    """

    ADDRESS_BESOK = "besøk"
    ADDRESS_PRIVATE = "private"
    ADDRESS_POST = "post"
    ADDRESS_OTHER_POST = "addr_other_post"
    ADDRESS_OTHER_BESOK = "addr_other_besok"

    country2ziplength = {
        "": 4, "NO": 4, "DK": 4
        }

    def __init__(self, kind, street=(), zip="", city="", country=""):
        self.kind = kind
        if isinstance(street, (list, tuple)):
            self.street = "\n".join(filter(None, map(unicode.strip, street)))
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
        if self.country not in (
                "CA",
                "GB",
                "IT",
                "NL",
                "NO",
                "RU",
                "SE",
                "US"):
            # TBD: Log it with the logger framework?
            self.country = None
        # fi

    def __str__(self):
        return "%s, %s, %s, %s, %s" % (self.kind, self.street, self.zip,
                                       self.city, self.country)


class DataContact(object):

    CONTACT_PHONE = "generic phone"
    CONTACT_FAX = "fax"
    CONTACT_URL = "url"
    CONTACT_EMAIL = "e-mail"
    CONTACT_PRIVPHONE = "private phone"
    CONTACT_MOBILE_WORK = "cell phone work"
    CONTACT_MOBILE_PRIVATE = "cell phone private"
    CONTACT_MOBILE_PRIVATE_PUBLIC = "cell phone private to display"

    """Class for storing contact information (phone, e-mail, URL, etc.)"""

    def __init__(self, kind, value, priority):
        self.kind = kind
        assert self.kind in (self.CONTACT_PHONE, self.CONTACT_FAX,
                             self.CONTACT_URL, self.CONTACT_EMAIL,
                             self.CONTACT_PRIVPHONE, self.CONTACT_MOBILE_WORK,
                             self.CONTACT_MOBILE_PRIVATE,
                             self.CONTACT_MOBILE_PRIVATE_PUBLIC)
        self.value = value
        self.priority = priority

    def __str__(self):
        return "contact (%s %s): %s" % (self.kind, self.priority, self.value)


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
        lang = lang and lang.lower() or lang
        self.language = lang

    def __str__(self):
        if self.language:
            return "%s: %s (%s)" % (self.kind, self.value, self.language)
        return "%s: %s" % (self.kind, self.value)


class NameContainer(object):
    """Class for keeping track of multiple names for an object.

    Names are indexed by name type -- first, middle, last, work title, OU
    name, etc. They may be multiple entries for the same type.
    """

    def __init__(self):
        self._names = dict()

    def validate_name(self, name):
        """By default all names are valid."""

        return True

    def add_name(self, name):
        """Add a new name.

        We can have several names of the same kind. If this happens, they are
        all chained together under the kind key.
        """

        self.validate_name(name)
        kind = name.kind

        if kind in self._names:
            self._names[kind].append(name)
        else:
            self._names[kind] = [name, ]

    def iternames(self):
        return self._names.iteritems()

    def get_name(self, kind, default=None):
        tmp = self._names.get(kind, default)
        return tmp

    def get_name_with_lang(self, kind, *priority_order):
        """Extract a name of given kind, respecting the given priority order.

        priority_order contains languages in the preferred order. If no
        language matches, we return None. NB! None is different from a name
        that is an empty string.
        """

        # Names without language come last
        max = len(priority_order)+1
        weights = {None: max, }
        for i, lang in enumerate(priority_order):
            weights[lang.lower()] = i

        # If we have no name of this kind at all, just return None at once.
        names = self._names.get(kind, None)
        if not names:
            return None

        names = filter(lambda x: x.language in priority_order, names)
        names.sort(lambda x, y: cmp(weights[x.language],
                                    weights[y.language]))
        if names:
            return names[0].value
        else:
            return None


class DataEmployment(NameContainer):
    """Class for representing employment information."""

    # Employment types
    HOVEDSTILLING = "hovedstilling"
    BISTILLING = "bistilling"
    GJEST = "gjest"
    BILAG = "bilag"

    # Emplyment categories
    KATEGORI_OEVRIG = "tekadm-øvrig"
    KATEGORI_VITENSKAPLIG = "vitenskaplig"

    # Work title string
    WORK_TITLE = "stillingstittel"

    def __init__(self, kind, percentage, code, start, end, place, category,
                 leave=None, mg=None, mug=None):
        """Create a new Employment object.

        :type kind: basestring
        :param kind: Employment type, one of the attributes of this class.

        :type percentage: float
        :param percentage: Employment percentage, 0.0 - 100.0

        :type code: int
        :param code: Employment code (stillingskode)

        :type start: mx.DateTime
        :param start: Start date of the employment

        :type end: mx.DateTime
        :param end: End date of the employment

        :type place: tuple
        :param place:
            Organizational unit where the employment belongs. A tuple
            consisting of (id-type, id). The id-type should be an attribute of
            DataOU.

        :type category: basestring
        :param category:
            Employment category, one of the attributes of this class.

        :type leave: list
        :param leave:
            Periods where the employment is inactive. List of dict(-like)
            objects. Each object should contain the keys 'start_date' and
            'end_date', with a mx.DateTime value.

        :type mg: int
        :param mg: (MEGType, medarbeidergruppe)

        :type mug: int
        :param mug: (MUGType, medarbeiderundergruppe)
        """
        super(DataEmployment, self).__init__()
        # TBD: Subclass?
        self.kind = kind
        assert self.kind in (self.HOVEDSTILLING, self.BISTILLING,
                             self.GJEST, self.BILAG)
        self.percentage = percentage
        self.code = code
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
        self.mg = mg
        self.mug = mug

    def is_main(self):
        return self.kind == self.HOVEDSTILLING

    def is_guest(self):
        return self.kind == self.GJEST

    def is_active(self, date=Date(*time.localtime()[:3])):
        # IVR 2009-04-29 Lars Gustav Gudbrandsen requested on 2009-04-22 that
        # all employment-related info should be considered active 14 days
        # prior to the actual start day.
        # Jazz 2011-03-23: In order to avoid revoking affiliations/priviledges
        # for people changing role/position at UiO we should let the
        # affiliation be valid for a few days after it has been revoked
        # in the authoritative source
        if self.start:
            return ((self.start - DateTimeDelta(14) <= date) and
                    ((not self.end) or (date <= self.end + DateTimeDelta(3))))

        return ((not self.end) or (date <= self.end + DateTimeDelta(3)))

    def has_leave(self, date=Date(*time.localtime()[:3])):
        """If the employment is on leave, e.g. working somewhere else
        temporarily.
        """
        for l in self.leave:
            if l['start_date'] <= date and (date <= l['end_date']):
                return True
        return False

    def __str__(self):
        return "(%s) Employment: %s%% %s [%s..%s @ %s]" % (
            self.kind, self.percentage,
            ", ".join("%s:%s" % (x[0], map(text_type, x[1]))
                      for x in self.iternames()),
            self.start, self.end, self.place)


class DataExternalWork(object):
    """Representing external employment or affiliation registered following the
    University of Oslo's regulations for external work."""
    def __init__(self, organization, type, extent, start, end, description):
        self.description = description
        self.organization = organization
        self.type = type
        self.extent = extent
        self.start = start
        self.end = end

    def __str__(self):
        return "Org: %s Type: %s Extent: %s Start: %s End: %s" % (
            self.organization,
            self.type,
            self.extent,
            self.start,
            self.end
        )


class DataEntity(NameContainer):
    """Class for representing common traits of objects in a data source.

    Typically, a subclass of DataEntity will be a Person or an OU.
    """
    def __init__(self):
        super(DataEntity, self).__init__()
        self._external_ids = dict()
        self._contacts = list()
        self._addresses = dict()

    def add_id(self, kind, value):
        self.validate_id(kind, value)
        self._external_ids[kind] = value

    def add_contact(self, contact):
        self._contacts.append(contact)

    def add_address(self, address):
        if address:
            self._addresses[address.kind] = address

    def iterids(self):
        return self._external_ids.iteritems()

    def itercontacts(self):
        return iter(self._contacts)

    def iteraddress(self):
        return self._addresses.iteritems()

    def get_contact(self, kind, default=list()):
        result = list()
        for contact in self.itercontacts():
            if contact.kind == kind:
                result.append(contact)
            # fi
        # od

        return result or default

    def get_id(self, kind, default=None):
        return self._external_ids.get(kind, default)

    def get_address(self, kind, default=None):
        return self._addresses.get(kind, default)


class DataOU(DataEntity):
    """Class for representing OUs in a data source."""

    NO_SKO = "sko"
    NO_NSD = "nsdkode"

    NAME_ACRONYM = "acronym"
    NAME_SHORT = "short"
    NAME_LONG = "long"

    def __init__(self):
        super(DataOU, self).__init__()
        self.parent = None
        # Whether this OU can be published in electronic catalogues
        self.publishable = False
        self.start_date = None
        self.end_date = None
        # This is just a collection of names. However the name API itself
        # supports single values of a given type only.
        self._usage_codes = set()

    def add_usage_code(self, code):
        if (
                hasattr(cereconf, "OU_USAGE_SPREAD") and
                code in cereconf.OU_USAGE_SPREAD
        ):
            self._usage_codes.add(code)

    def iter_usage_codes(self):
        return iter(self._usage_codes)

    def validate_id(self, kind, value):
        assert kind in (self.NO_SKO, self.NO_NSD,)

    def validate_name(self, name):
        assert name.kind in (self.NAME_ACRONYM,
                             self.NAME_SHORT,
                             self.NAME_LONG)

    def __unicode__(self):
        return "DataOU (valid: %s-%s): %s\n| %s\n| %s\n| %s\n__%s\n" % (
            self.start_date,
            self.end_date,
            list(self.iterids()),
            ["%s:%s" % (x, map(unicode, y)) for x, y in self.iternames()],
            map(unicode, self.itercontacts()),
            list(self._usage_codes),
            ["%s:%s" % (x, unicode(y)) for x, y in self.iteraddress()])

    def __str__(self):
        return self.__unicode__().encode('utf-8')


class DataPerson(DataEntity):
    """Class for representing people in a data source."""

    # TBD: Cerebrum constants?
    NAME_FIRST = "FIRST"
    NAME_LAST = "LAST"
    NAME_MIDDLE = "MIDDLE"
    NAME_TITLE = "personal title"
    NO_SSN = "NO SSN"
    GENDER_MALE = "M"
    GENDER_FEMALE = "F"
    GENDER_UNKNOWN = "X"

    PASSNR = "Passport ID"

    def __init__(self):
        super(DataPerson, self).__init__()

    def validate_id(self, kind, value):
        assert kind in (self.NO_SSN, self.PASSNR)

    def validate_name(self, name):
        assert name.kind in (self.NAME_FIRST, self.NAME_LAST, self.NAME_MIDDLE,
                             self.NAME_TITLE)

    def __unicode__(self):
        ret = "DataPerson: %s\n" % list(self.iterids())
        for kind, name in self.iternames():
            # ret += "%s: %s\n" % (kind, name.value)
            ret += "| %s: %s\n" % (kind, map(unicode, name))
        ret += "__\n"
        return ret

    def __str__(self):
        return self.__unicode__().encode('utf-8')


class HRDataPerson(DataPerson):
    """Class for representing employees in a data source."""

    def __init__(self):
        super(HRDataPerson, self).__init__()

        self.gender = None
        self.birth_date = None
        self.employments = list()
        self.reserved = None
        self.external_work = list()

    def add_employment(self, emp):
        self.employments.append(emp)

    def add_external_work(self, emp):
        self.external_work.append(emp)

    # IVR 2007-03-06 FIXME: ugh! name consistency was not a top priority to
    # say the least :( There should be a "_" here.
    def iteremployment(self):
        return iter(self.employments)

    def has_active_employments(self, timepoint=Date(*time.localtime()[:3])):
        """Decide whether this person has employments at a given timepoint."""

        for x in self.iteremployment():
            if (
                    (
                        x.kind in (x.HOVEDSTILLING, x.BISTILLING) and
                        x.is_active(timepoint)
                    ) or
                    # IVR 2007-01-19 FIXME:
                    # This is a horrible, gruesome, vile,
                    # ugly, repulsive and hairy pile of crud.
                    # It MUST DIE, once we get rid of LT.
                    (x.kind == x.GJEST and x.code == "POLS-ANSAT")
            ):
                return True

        return False

    def __str__(self):
        spr = super(HRDataPerson, self).__str__()
        result = (
            "HRDataPerson: %s\n"
            "| gender: %s\n"
            "| birth: %s\n"
            "| address: %s\n"
            "| employment: %s\n__\n" % (
                spr,
                self.gender,
                self.birth_date,
                ['%s: %s' % x for x in self.iteraddress()],
                [str(x) for x in
                 list(self.iteremployment())]
            )
        )
        # if self.external_work:
        #     result += "\n| external work: %s" % map(str, self.external_work)
        return result


class AbstractDataGetter(object):
    """
    An abstraction layer for information extraction from various authoritative
    systems.

    This class operates in terms of DataPerson, DataOU, DataGroup and the
    like. It relies exclusively on the information available through these
    interfaces.
    """

    def __init__(self, logger, fetchall=True):
        """Initialize the data source extractor.

        fetchall decides whether the data is fetched incrementally or is
        loaded entirely into memory (cf. db_row).
        """

        self.logger = logger
        self.fetch(fetchall)

    def fetch(self, fetchall=True):
        """Connect to data source and fetch data."""
        raise NotImplementedError("fetch not implemented")

    def iter_person(self):
        """Give an iterator over person objects in the data source."""
        raise NotImplementedError("iter_person not implemented")

    def iter_ou(self):
        """Give an iterator over OU objects in the data source."""
        raise NotImplementedError("iter_ou not implemented")


class XMLDataGetter(AbstractDataGetter):
    """This class provides abstractions to operate on XML files."""

    def __init__(self, filename, logger, fetchall=True):
        self._filename = filename
        self._data_source = None
        self._encoding = get_xml_file_encoding(filename)

        super(XMLDataGetter, self).__init__(logger, fetchall)

    def _make_iterator(self, element, klass, **kwargs):
        """Create an iterator over XML elements.

        Creates an iterator over XML elements 'element' that returns instances
        of class klass.
        """

        if self._data_source:
            it = self._data_source.iter(element)
        else:
            it = XMLEntityIterator(self._filename, element)

        return klass(iter(it), self.logger, self._encoding, **kwargs)

    def fetch(self, fetchall=True):
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


class XMLEntity2Object(object):
    """A small helper for common XML -> Data*-class conversions.

    The subclasses of this class have to implement one method, essentially:
    next_object(element). This method should create an object (an instance of
    DataEntity) that is the representation of an XML subtree. If for some
    reason such an object cannot be created, None must be returned.
    """

    def __init__(self, xmliter, logger, encoding, **kwargs):
        """Constructs an iterator supplying DataEntity objects.

        xmliter is the the underlying ElementTree iterator (here we do not
        care if it is in-memory or on file).
        """

        self._xmliter = iter(xmliter)
        self.logger = logger
        self.encoding = encoding
        for (k, v) in kwargs.items():
            setattr(self, k, v)

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

        import sys
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
                    self.logger.warn(
                        "%s occurred while processing XML element %s. "
                        "Skipping it.",
                        Utils.format_exception_context(*sys.exc_info()),
                        element.tag)
                element.clear()

    @staticmethod
    def exception_wrapper(functor, exc_list=None, return_on_exc=None):
        """This is a convenience method for Utils.exception_wrapper.

        IVR 2008-03-12 Sorry, some magic ahead to make code elsewhere simpler
        to use.

        The goal of this method is to make it easier to bind loggers to
        wrapped methods. Although this method is static *and* it refers to
        self.logger (which does not really make any sense), the code WILL work
        on any instance of this class (or its subclasses), since all of these
        instances do in fact have a 'logger' attribute and the wrapped method
        (i.e. L{functor}) will be called on an instance (it is a bound
        method). IOW, this class and its subclasses are the sole target
        audience for this method.

        Check sapxml2object.py for some use cases.

        Caveat: for static methods this wrapper WILL FAIL! I.e. functor *must*
        be a non-static method of a subclass of this class.

        The parameters have the same meaning as L{Utils.exception_wrapper}.

        The return value is the same as with L{Utils.exception_wrapper}.
        """

        def wrapper(self, *rest, **kw_args):
            # This gives us a wrapped method that ignores the suitable
            # exceptions ...
            func = Utils.exception_wrapper(functor, exc_list, return_on_exc,
                                           self.logger)
            # ... and here we call the wrapped method.
            return func(self, *rest, **kw_args)

        return wrapper

    def __iter__(self):
        return self

    def _make_mxdate(self, text, format="%Y%m%d"):
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


class XMLEntityIterator(object):
    """Iterate over an XML file and return complete elements of a given kind.

    Iterative parsing in ElementTree is based on (event, element) pairs. For
    dealing with people, OUs and the like, we need look at ('end',<ElementTree
    'something'>) only, where 'something' represents the entity we are
    interested in. In a sense, this class iterates over XML subtrees.
    """

    def __init__(self, filename, element):
        # iterparse itself is not necessarily an iterator. Therefore iter()
        self.it = iter(iterparse(filename, (str("start"), str("end"))))
        self.element_name = element

        # Keep track of the root element (to prevent element caching)
        junk, self._root = self.it.next()

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

    def __iter__(self):
        return self
