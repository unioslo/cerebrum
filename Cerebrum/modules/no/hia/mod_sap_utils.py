#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2017 University of Oslo, Norway
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

""" Module with utilities for dealing with SAP-specific data files.

The public interface is two methods only -- `make_person_iterator` and
`make_employment_iterator`. The rest is meant for internal usage only.

SAPTupleBase and its descendants provide a tuple/dict-like interface to DFØ's
SAP data.

TODO: This module should be profiled.

"""

import re
import sys
from datetime import datetime


def make_passnr_iterator(source, logger=None):
    """Iterator for passnr SSØ-SAP person data.

    @param source:
      Any iterable yielding successive lines with person data.
    """
    for line in source:
        tpl = _sap_row_to_tuple(line)
        yield _SAPPersonDataTuplePassnr(tpl, logger)


#
# Public interface for this module
#
def make_person_iterator(source, fok=False, logger=None):
    """Iterator for grokking SSØ-SAP person data.

    @param source:
      Any iterable yielding successive lines with person data.

    @param fok:
      boolean determining whether to respect forretningsområdekode field.
    """
    if fok:
        kls = _SAPPersonDataTupleFok
    else:
        kls = _SAPPersonDataTuple

    for line in source:
        tpl = _sap_row_to_tuple(line)
        yield kls(tpl, logger)


def make_employment_iterator(source, fok, logger=None):
    """Iterator for grokking SSØ-SAP employment data.

    @param source:
      Any iterable yielding successive lines with employment data.

    @param fok:
      See L{make_person_iterator}
    """

    if fok:
        kls = _SAPEmploymentTupleFok
    else:
        kls = _SAPEmploymentTuple

    for line in source:
        tpl = _sap_row_to_tuple(line)
        yield kls(tpl, logger)


def make_utvalg_iterator(source, fok, logger=None):
    """Iterator for getting SSØ-SAP utvalg data about persons.

    @param source:
        Any iterable yielding successice lines with utvalg data.

    @param fok:
        See L{make_person_iterator}

    """
    if not fok:
        raise Exception('Not implemented')
    kls = _SAPUtvalgTuple
    for line in source:
        tpl = _sap_row_to_tuple(line)
        yield kls(tpl, logger)


def load_expired_employees(source, fok, logger=None):
    """Collect SAP IDs for all expired employees from source."""

    it = make_person_iterator(source, fok, logger)
    result = set()
    for tpl in it:
        if tpl.expired():
            result.add(tpl.sap_ansattnr)

    return result


def load_invalid_employees(source, fok, logger=None):
    """Collect SAP IDs for all invalid employees from source."""
    return set(tpl.sap_ansattnr for tpl in
               make_person_iterator(source, fok, logger) if not tpl.valid())


def _make_sequence(something):
    """Create a sequence out of something.

    If something *is* a sequence (list, tuple or set), leave it as
    is. Otherwise return a tuple with 1 element -- something.
    """

    if isinstance(something, (list, tuple, set)):
        return something
    return (something,)


def _with_strip(index):
    """Small rule helper.

    Return a pair -- index and a lambda strip()ing the value at that index.
    """
    return (index, lambda value: value.strip() or None)


class _MetaTupleBase(type):

    """Metaclass for SAP rule manipulation.

    This metaclass is useful for creating rules for processing tuples made out
    of lines of SAP-SSØ data.

    Classes with SAP rules can inherit from _SAPTupleBase. Each class defines
    2 class attributes, _field_count and _field_rules. The former is the
    number of items per SAP tuple representing one logical entry. The latter
    is a set of rules for processing such tuples.

    Classes using this metaclass construct values from tuples based on the
    ruleset in _field_rules. The sole reason to bother with metaclasses is to
    allow inheritance hierarchies to use each other's rules:

    class A(SAPTupleBase):
        _field_count = 3
        _field_rules = { 'foo': 0,
                         'bar': ((1, 2),
                                 lambda *rest: "".join(str(x) for x in rest)),
        }

    class B(A):
        _field_count = 5
        _field_rules = { 'bar': (3, int), }


    x = A(('a', 'b', 'c'))
    print 'A() instance::', x.foo, x.bar

    y = B(('d', 'e', 'f', 10, 11))
    print 'B() instance::', y.foo, y.bar

    ... yields:

    A() instance:: a bc
    B() instance:: d 10

    So, instances of B 'inherit' the rule for attribute 'foo' from A, but
    define their own rule for attribute 'B'.

    IT'S NOT MORE MAGIC THAN THIS.
    """

    def __new__(cls, name, bases, dct):
        kls = type.__new__(cls, name, bases, dct)

        def identity(x):
            return x

        # Load the superclasses' rules...
        tmp = dict()
        for base in kls.__bases__:
            if hasattr(base, "_field_rules"):
                tmp.update(base._field_rules)

        # Encourage lazyness -- if there is one superclass only, AND we did
        # not bother to define our own counter for fields, inherit the
        # baseclass' version
        if (not hasattr(kls, "_field_count") and
            len(kls.__bases__) == 1 and
                hasattr(kls.__bases__[0], "_field_count")):
            kls._field_count = kls.__bases__[0]._field_count

        # Now fix up our own. Note that if the superclass has already defined
        # a rule for an item, we'll overwrite it here...
        if hasattr(kls, "_field_rules"):
            rules = kls._field_rules
            for item in rules:
                action = _make_sequence(rules[item])
                item_index = _make_sequence(action[0])

                # no transformation, just return the field as is
                if len(action) == 1:
                    item_transformation = identity
                elif len(action) == 2:
                    item_transformation = action[1]
                else:
                    raise RuntimeError("Wrong format for item: %s" % str(item))

                tmp[item] = (item_index, item_transformation)

        kls._field_rules = tmp
        return kls


class _SAPTupleBase(object):

    """A tuple/dict-like class for abstracting away SAP-data.

    This class presents and abstraction layer to deal with SAP-data. The main
    goal is to abstract away the storage details for SAP files. Ideally, we
    should be able to swap XML, CSV, etc without affecting the client code.

    The inspiration for this class is db_row and collections.namedtuple().

    Each instance represents one logical row of information (typically
    covering one employee or one employment record). Each row's raw individual
    fields are accessible by the numeric key:

      >>> x = SAPTupleBase(<some tuple>)
      >>> x[3]
      ...

    ... will give access to the fourth element in the tuple.

    Additionally, if so desired, some fields may be named and accessed by
    their respective names (check SAPPersonDataTuple, e.g.). Furthermore, a
    transformation function may be applied to a named field, if so desired:

      >>> x = SAPEmploymentTuple(<some tuple>)
      >>> x[5]
      20100228
      >>> x.start_date
      <mx.DateTime.DateTime object for '2010-02-28 00:00:00.00'>
      >>> x['start_date'']
      <mx.DateTime.DateTime object for '2010-02-28 00:00:00.00'>

    Both kinds of index/key refer to the same element, but positional access
    yields raw value, whereas accessing the attribute by name provides the
    processed version.

    Processing is especially useful, if the transformation is non-trivial
    and/or involves multiple fields.

    Should the transformation fail, the slot will be set to None and a
    suitable warning issued.
    """

    #
    # Make sure everyone's _field_count/_field_rules are processed properly on
    # loading.
    __metaclass__ = _MetaTupleBase

    def __init__(self, tpl, logger=None):
        if len(tpl) != self._field_count:
            raise RuntimeError("Wrong # of fields: wanted %s got %s" %
                               (self._field_count, len(tpl)))

        for slot_name in self._field_rules:
            indices, transformation = self._field_rules[slot_name]
            try:
                value = transformation(*[tpl[index] for index in indices])
                setattr(self, slot_name, value)
            except:
                if logger is not None:
                    logger.info("Failed to set value %s for attribute %s in "
                                "tuple (%s): %s. Assuming None",
                                ",".join(tpl[index] for index in indices),
                                slot_name,
                                tpl,
                                sys.exc_info()[1])
                setattr(self, slot_name, None)

        self._tuple = tuple(tpl)

    def __str__(self):
        name = "%s instance" % (self.__class__.__name__,)
        field_count = "%s field(s)" % (self._field_count,)
        values = ", ".join("%s=%s" % (k, getattr(self, k))
                           for k in self._field_rules)
        return "%s: %s, %s" % (name, field_count, values)

    def __getitem__(self, idx):
        """Allow tuple and dict-like access."""

        return self._tuple[idx]

    # TBD: __setitem__ ?
    # def __setitem__(self, key, value):
    #    pass


class _SAPPersonDataTuplePassnr(_SAPTupleBase):

    """Adaptor class for MD2_Persondata_status.csv.

    The field split looks like this:


      Field  Description
       5   SAP person ID
      49   Passport number
      50   Passport country code
    """
    _field_count = 77
    _field_rules = {
        'sap_ansattnr': 5,
        'sap_passnr': _with_strip(49),
        'sap_passcountry': _with_strip(50),
    }


class _SAPPersonDataTuple(_SAPTupleBase):

    """Adaptor class for feide_persondata.txt.

    The field split looks like this:

      Field  Description
       0   SAP person ID
       2   Employment termination date
       3   Name initials
       4   SSN / norwegian fødselsnr
       5   Birth date
       6   First name
       7   Middle name
       8   Last name
      12   Contact phone private
      13   Contact phone
      14   Contact phone cellular
      15   Contact phone cellular - private
      18   Bostedsadr. C/O
      19   Bostedsadr. Gate
      20   Bostedsadr. husnr.
      21   Bostedsadr. Tillegg
      22   Bostedsadr. Poststed
      23   Bostedsadr. postnr.
      24   Bostedsadr. Land
      25   Forretningsområde ID
      26   Office building code
      27   Office room number
      28   Work title
    """

    _field_count = 39
    _field_rules = {'sap_ansattnr': 0,
                    'sap_termination_date': (2, lambda x: x and
                                             datetime.strptime(x, "%Y%m%d")
                                             or None),
                    'sap_fnr': 4,
                    # <- defer fnr check to later
                    'sap_birth_date': (5, lambda x:
                                       datetime.strptime(x, "%Y%m%d")),
                    'sap_middle_name': _with_strip(7),
                    'sap_first_name': ((6, 7),
                                       lambda x, y: y and x.strip() + " " +
                                       y.strip() or x.strip()),
                    'sap_last_name': _with_strip(8),
                    'sap_initials': _with_strip(3),
                    'sap_personal_title': _with_strip(28),
                    'sap_phone_private': _with_strip(12),
                    'sap_phone': _with_strip(13),
                    'sap_phone_mobile': _with_strip(14),
                    'sap_phone_mobile_private': _with_strip(15),
                    'sap_fax': _with_strip(29),
                    'sap_address': (range(18, 22),
                                    lambda *rest: ", ".join(x.strip()
                                                            for x in rest) or
                                    None),
                    'sap_zip': _with_strip(23),
                    'sap_city': _with_strip(22),
                    'sap_country': _with_strip(24),
                    'sap_building_code': _with_strip(26),
                    'sap_roomnumber': _with_strip(27),
                    'sap_publish_tag': _with_strip(36), }

    def expired(self):
        """Is this entry expired?"""
        return (self.sap_termination_date and
                (self.sap_termination_date < datetime.now()))

    # TODO: Should this really just return True?
    def valid(self):
        """Is this entry to be ignored?"""
        return True

    def reserved_for_export(self):
        """Whether this person is reserved from export to catalogue
        services."""
        return (self.sap_publish_tag and
                (self.sap_publish_tag != "Kan publiseres"))


class _SAPPersonDataTupleFok(_SAPPersonDataTuple):
    """This one has forretningsområdekode."""

    _field_rules = {'sap_fokode': 25, }

    def valid(self):
        """Everything tagged with fok"""
        if (not self.sap_fokode) or self.sap_fokode == '9999':
            return False
        return True


class _SAPEmploymentTuple(_SAPTupleBase):

    """Adaptor class for feide_persti.txt.

    The field split looks like this:

      Field  Description
        0     SAP person ID
        1     orgeh (magic number constituting part of the SAP OU id)
        2     funksjonstittel (magic employment code)
        3     lonnstittel     (magic employment code)
        4     forretningsområdekode (magic number constituting part of the SAP
              OU id)
        5     Employment start date
        6     Employment end date
        7     Employment type (hoved-/bistilling)
        8     Employment percentage (0-100, as a float)
    """

    _field_count = 9
    _field_rules = {'sap_ansattnr': 0,
                    'funksjonstittel': 2,
                    'lonnstittel': 3,
                    'start_date': (5, lambda x:
                                   datetime.strptime(x, "%Y%m%d").date()),
                    'end_date': (6, lambda x:
                                 datetime.strptime(x, "%Y%m%d").date()),
                    'stillingstype': 7,
                    'percentage': (8, float),
                    'sap_ou_id': 1, }

    def valid(self):
        # '99999999' comes from SAP / "Stillnum"
        return self.funksjonstittel != '99999999'


class _SAPEmploymentTupleFok(_SAPEmploymentTuple):
    """This time with forretningsområdekode."""

    _field_rules = {'sap_fokode': 4,
                    'sap_ou_id': ((1, 4), lambda x, y: "%s-%s" % (x, y))}

    def valid(self):
        # "9999" comes from SAP
        if (not self.sap_fokode) or self.sap_fokode == "9999":
            return False
        return super(_SAPEmploymentTupleFok, self).valid()


class _SAPUtvalgTuple(_SAPTupleBase):

    """Abstracting away 'utvalg' data from SAP, from feide_perutvalg.txt.

    The field split looks like this:

      Field  Description
        0    SAP person ID
        1    Seksjonstilhørighet - forretningsområde ID? - orgeh?
        2    Ansattkode (vert erstatta av MEG/MUG) - employment type?
        3    Fagmiljø
        4    Start date
        5    End date
        6    Role

    """

    _field_count = 7
    _field_rules = {'sap_ansattnr': 0,
                    'sap_orgeh': 1,
                    'sap_unknown': 2,
                    'sap_fagmiljo': 3,
                    'sap_start_date': (4, lambda x: x and
                                       datetime.strptime(x, "%Y%m%d")
                                       or None),
                    'sap_termination_date': (5, lambda x: x and
                                             datetime.strptime(x, "%Y%m%d")
                                             or None),
                    'sap_role': 6, }

    def expired(self):
        """Is this entry expired?"""
        return (self.sap_termination_date and
                (self.sap_termination_date < datetime.now()))

    def valid(self):
        """Is this entry to be ignored?"""
        return (not self.sap_start_date) or (self.sap_start_date <
                                             datetime.now())


def _sap_row_to_tuple(sap_row):
    """Split a line into fields delimited by ';'.

    NB! ';' may be escaped. The escape character is backslash. When
    such an escaped ';' occurs, it is replaced by a regular ';' in the
    value returned to the caller.
    """

    # (?<!...) is negative lookbehind assertion. It matches, if the
    # current position is not preceded by ...
    fields = re.split(r'(?<!\\);', sap_row.strip())

    # We split by ";", unless it is escaped, in which case it is kept
    return tuple(field.replace(r'\;', ';') for field in fields)


def _tuple_to_sap_row(tpl):
    """This is the converse of sap_row_to_tuple."""
    return ";".join(field.replace(';', r'\;') for field in tpl)
