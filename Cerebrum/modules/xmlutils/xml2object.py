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
* Timing of LT-converter vs. earlier import strategies (xml.sax + dict
  manipulation).
* Decision on sko-representation. I do not think a simple string would do,
  as a sko is often regarded as a tuple or as a dict. We need something more
  flexible.
"""

import copy
import re
import sys
import time
import types

from cElementTree import parse, iterparse
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

    def __init__(self):
        super(DataOU, self).__init__()
        self.parent = None
        # Whether this OU can be published in electronic catalogues
        self.publishable = False
        self.start_date = None
        self.end_date = None
    # end __init__


    def validate_id(self, kind, value):
        assert kind in (self.NO_SKO, self.NO_NSD)
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

    An implementation must make sure that the data stream might be traversed
    multiple times (e.g. to consecutive search()s must scan the entire data
    stream twice).
    """

    def __init__(self, fetchall = True):
        """Initialize the data source extractor.

        fetchall decides whether the data is fetched incrementally or is
        loaded entirely into memory (cf. db_row).
        """
        
        self.fetch(fetchall)
    # end __init__


    def fetch(self, fetchall = True):
        """Connect to data source and fetch data."""
        raise NotImplementedError("fetch not implemented")
    # end fetch
    
    
    def search_persons(self, predicate):
        """List all persons matching given criteria."""

        for person in self.iter_persons():
            if predicate(person):
                # TBD: Do we want a generator here?
                yield person
            # fi
        # od
    # end search_persons


    def list_persons(self):
        """List all persons available from the data source."""
        return list(self.iter_persons())
    # end list_persons


    def iter_persons(self):
        """Give an iterator over people objects in the data source."""
        raise NotImplementedError("iter_persons not implemented")
    # end iter_persons

            
    def search_ou(self, predicate):
        """List all OUs matching given criteria."""

        for ou in self.iter_ou():
            if predicate(ou):
                yield ou
            # fi
        # od
    # end search_ou


    def list_ou(self):
        """List all OUs available from the data source."""
        return list(self.iter_ou())
    # end list_ou


    def iter_ou(self):
        """Give an iterator over OU objects in the data source."""
        raise NotImplementedError("iter_ou not implemented")
    # end iter_ou
# end AbstractDataGetter



class XMLDataGetter(AbstractDataGetter):
    """This class provides abstractions to operate on XML files."""

    def __init__(self, filename, fetchall = True):
        self._filename = filename
        self._data_source = None

        super(XMLDataGetter, self).__init__(fetchall)
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
        # fi

        return klass(iter(it))
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
        # fi
    # end fetch
# end XMLDataGetter



class XMLEntity2Object(object):
    """A small helper for common XML -> Data*-class conversions."""

    def __init__(self, xmliter):
        """Constructs an iterator supplying DataEntity objects.

        xmliter is the the underlying ElementTree iterator (here we do not
        care if it is in-memory or on file).
        """

        self._xmliter = iter(xmliter)
    # end __init__


    def next(self):
        return self._xmliter.next()
    # end next


    def _make_mxdate(self, text, format = "%Y%m%d"):
        if not text:
            return None
        
        year, month, day = time.strptime(text, format)[:3]
        return Date(year, month, day)
    # end _make_mxdate


    def __iter__(self):
        return self
    # end __iter__
# end XMLEntity2Object


    
class XMLEntityIterator:
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
        """Return next specified element, ignoring all else."""
        
        # Each time next is called, we drop whatever is dangling under
        # root. It might be problematic if there is *a lot* of elements
        # between two consecutive self.element_name elements.
        self._root.clear()
        
        for event, element in self.it:
            if event == "end" and element.tag == self.element_name:
                return element
            # fi
        # od

        raise StopIteration
    # end next
                

    def __iter__(self):
        return self
    # end __iter__
# end XMLEntityIterator



class SkippingIterator:
    """Iterate over elements while ignoring exceptions.

    This comes in handy when we simply want to log and skip erroneous
    entries. If no logging is desired, set logger to None. No indication of
    failure would be provided (erroneous elements are going to be silently
    ignored).
    """

    def __init__(self, iterator, logger):
        self.iterator = iterator
        self.logger = logger

        # IVR 2007-07-18 FIXME: These are the errors that we want to ignore,
        # since
        # 1) there are too many of them
        # 2) they are known and they will not be fixed in the nearest future
        # 
        # The format of this dictionary is <ErrorType>: list of regexs
        # ... where <ErrorType> specifies the exception type and list of regexs
        # represents the specific values of the exceptions we want to ignore.
        from Cerebrum.modules.no import fodselsnr
        self.ignore_errors = {
            fodselsnr.InvalidFnrError:
                # temporary fnrs that are known to fail fnr checksum
                [re.compile("\d{6}00[0,1,2]00"), ],
            ValueError:
                # this is how SAP/POLS tag invalid person entries
                [re.compile("Name contains '\*'")],
            AssertionError:
                # These OUs are broken, since they lack the proper names
                [re.compile("No name available for OU \(0, 0, 0\)")],
            }

    def __iter__(self):
        return self

    def next(self):
        while 1:
            try:
                element = self.iterator.next()
                return element
            except StopIteration:
                raise
            except:
                exc, value, tb = sys.exc_info()
                # it's not one of the "known" errors
                if exc not in self.ignore_errors:
                    self.logger.exception("failed to process next element")
                    continue

                value = str(value)
                matched = False
                for pobj in self.ignore_errors[exc]:
                    if pobj.search(value):
                        self.logger.debug("(Known) error for next element. "
                                          "Element ignored: %s %s", str(exc), value)
                        matched = True
                        break

                # It's not a "known" error
                if not matched:
                    self.logger.exception("failed to process next (known) element")
                    continue
# end SkippingIterator
