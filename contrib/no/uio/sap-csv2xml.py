#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright 2011 University of Oslo, Norway
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

"""This script converts a SAPUiO csv file to an XML file.

Every day, SAPUiO hands Cerebrum a file with employee data. That file is an
ungodly bastard of something that looks like csv. This script converts that
file into an XML file that sapxml2object.py/import_HR_person.py can work with.

Cerebrum has never received a formal specification for this csv-bastard, so
all the actions in here are a product of guesswork. It is paramount that any
deviation from this guesswork is trapped and reported, rather than silently
glossed over.

Format
-------
The source file is iso-8859-1 encoded. It contains a sequence of records. Each
record can represent either a person or an OU. Within each record there may be
several subrecords. The legal subrecord types depend on the type of the parent
record:

  - Person subrecords: PERSON_ADDRESS, PERSON_BISTILLING, PERSON_COMM,
                       PERSON_HOVEDSTILLING, PERSN_ROLLS
  - OU subrecords: STED_STEDNAVN0, STED_STEDADDRESS, STED_STEDKOMM0, 
                   STED_STEDBRUK0

Both records and subrecords may have a number of fields associated with them
(note that a a record may have both fields and subrecord(s) (with
fields)). Fields are separated with ';'. We have no idea how ';' is quoted, if
it is part of the actual data.

For each subrecord, the possible fields that can be encountered within that
subrecord are fixed. E.g. for a PERSON_COMM, there are about 20-ish
possibilities (phone, e-mail, fax, etc.). **Any** deviation from such a fixed
list must be trapped and the entire parent record skipped. A notable exception
to this rule is language information. Some subrecords (HOVEDSTILLING,
BISTILLING) and some records (PERSON) carry language data. A priori there is
no upper limit on the number of fields in these lines. However, the language
data comes in pairs of fields -- language code followed by the actual value.

The relation between records/subrecords and lines is somewhat convoluted. Each
record starts with a specific header at the first character of a
line. Subsequent subrecords belonging to that record are indented with 8
spaces from the beginning of the line. However, the line length is fixed. If a
record/subrecord is longer than this limit (no one knows what the limit is),
the record/subrecord's 'continuation' is indented as well. I.e. care must be
taken when interpreting a new line:

  * If it's not indented AND it starts with a special Person/OU tag, then that
    line represents the start of the next Person/OU record.
  * If it's indented AND it starts with a special subrecord marker (such as
    STED_STEDKOMM), then that line represents the start of the next subrecord
    for the Person/OU record we are currently processing.
  * Otherwise it's a continuation of the previous line and should be adjoined
    to it (while stripping the leading 8 characters). 

The very first person record is additionally tagged with a '*'. The very first
OU record is also tagged with a '*' (we are not guaranteed that it's the case;
but empirical observation seems to support this).

Note that the record and subrecord markers act as synchronisation points. If
we meet a (sub)record where the the number of fields is incompatible with our
assumptions about that (sub)record, the code skips forward until the next
suitable entry (typically, next subrecord or next record). This way, we can
cope with occasional not too evil formatting errors (they do happen on regular
basis).

Unfortunately this synchronisation means that if somebody changes one of their
attributes to match one of the (sub)record markers, we could potentially be in
trouble (<http://xkcd.com/327/> seems relevant at this point).
"""

import csv
import getopt
import sys
import types
import re
from cStringIO import StringIO as IO


import cerebrum_path
import cereconf

from Cerebrum.extlib import xmlprinter
from Cerebrum.Utils import Factory
from Cerebrum.Utils import SimilarSizeWriter





# subrecords are indented (I have no idea what could have possibly compelled
# such brain damage)
INDENTATION = 8

#
# The csv uses this as separator
DELIMITER = ';'

# List of valid markers/tags that can be encountered "within" record/subrecord
# for a person and an OU.
valid_person_content = (u"PERSON_ADDRESS", u"PERSON_BISTILLING", u"PERSON_COMM",
                      u"PERSON_HOVEDSTILLING", u"PERSON_ROLLS")
valid_ou_content = (u"STED_STEDNAVN0", u"STED_STEDADDRESS", u"STED_STEDKOMM0",
                    u"STED_STEDBRUK0")
valid_record_markers = (u"PERSON_INFO", u"STED_STEDKODE", u"*PERSON_INFO",
                        u"*STED_STEDKODE")

#
# Delta (in %) we allow between 2 runs
OUTPUT_SIZE_DELTA = 10

#
#
INPUT_ENCODING = u"iso-8859-1"

#
#
OUTPUT_ENCODING = u"utf-8"




def collector(fields, tags, names_in_order, legal_values={}):
    """Construct a sequence of dicts out of a bunch of csv fields.

    In other words, this function turns this:

    TAG, value1, value2, ... valueN, TAG, value_2_1, value_2_2, ... value_2_N

    ... into this:

    [{name1: value1, name2: value2, ..., nameN: valueN},
     {name1: value_2_1, name2: value_2_2, ..., nameN: value_2_N},
     ... ]

    fields may contain several (not just one) logical entry. E.g. fields may
    have data for multiple contact information items.

    L{names_in_order} decides how to interpret L{fields}. We expect L{fields}
    to have some number of len(names_in_order) fields in order, separated by
    something that looks like tag. I.e.:

    TAG, datum1, datum2, TAG, datum3, datum4, TAG, datum5, datum6

    ... then we collect every datum_i, datum_{i+1}. Each of the (in this case)
    pairs represents a different item, and TAG acts like a separator.

    @type fields: sequence of basestring
    @param fields:
      Fields that we are interested it. fields contains a number of L{tag}s,
      and the L{tag}s are thrown away during parsing. The values themselves
      are ordered in the same sequence as L{names_in_order}.

    @type tag: sequence of basestrings or a basestring
    @param tag:
      L{tag} acts as a separator for data in fields. There may be multiple
      values specified here, in which case they are all considered equal.

    @type names_in_order: sequence of basestring
    @param names_in_order:
      Names for the fields we exract. These will be output as XML elements in
      the resulting XML file.

    @legal_values: dict (basestring -> sequence of whatever)
    @legal_values:
      If not None, this dict describes the values we are willing to accept
      for L{names_in_order}. I.e. if a tag, 'FOO' is a part of
      L{names_in_order}, and we want to assert that the only legal values for
      that tag are 'BAR', 1 and 2, then L{legal_values} should contain this
      entry::

        legal_values['FOO'] = ('BAR', 1, 2).

      No checks are performed on the *order* of legal values (i.e. we don't
      assert that 'BAR' comes before 1), only that the values associated with
      a given tag come from a certain value domain.

      This check is useful to trap bogus values of some of the attributes in
      the file.

    @rtype: sequence of dicts (from basestring to basestring)
    @return:
      Each dict represents an XML subtree to output. Each pair K, V in the
      dict becomes <K>V</K> in the XML file. Have a look at what sap2bas.xml
      looks like, and you'll see when this is useful.
    """

    def field_matches_tag(field, tags):
        if not isinstance(tags, (list, tuple, set)):
            tags = [tags,]
        # [:len(tag)] to allow STED_STEDNAVN0 to match STED_STEDNAVN
        for tag in tags:
            if field[:len(tag)] == tag:
                return True
        return False

    # +1 for the tag. The rest is the actual data we want to output.
    count = len(names_in_order) + 1
    collect = list()

    # The data is so fubar, that we may have more values between tags than
    # len(names_in_order). If that happens we are essentially fucked, and the
    # only recourse is to drop everything until the next tag is found.
    i = 0
    while i < len(fields):
        if not field_matches_tag(fields[i], tags):
            # we expected to see an tag (separator), but we don't => fuck
            # this record. 
            raise ValueError("Wrong # of items between tags for tag %s: %s" %
                             (tags, fields))

        # +1, to correct for the fact that L{tag}s are interspersed with data.
        tmp = dict((name, fields[i+index+1])
                   for index, name in enumerate(names_in_order)
                   if i+index+1 < len(fields))
        # if we see fewer fields than names_in_order dictates => the record is
        # incomplete => fuck this record.
        if len(tmp) != len(names_in_order):
            raise ValueError("Too few items after tags %s at the end of %s" %
                             (tags, fields))

        # Check the values for specified constraints.
        for name in tmp:
            # not in legal_values -> no constraints on the values
            if name not in legal_values:
                continue

            if tmp[name] not in legal_values[name]:
                raise ValueError("Aiee! tag=%s, value=%s not in legal_values" %
                                 (name, tmp[name]))
        collect.append(tmp)
        i += count

    return collect
# end collector



def output_to_xml(xml_tag, value, out):
    """Output something to XML sink L{out}.

    Once we've constructed a structure in memory representing the next logical
    record from the CSV file, we use this function to 'flatten' that structure
    onto an XML file.

    @param xml_tag: XML tag name which would surround whatever L{value} is.

    @param value: Value to output. Could be a scalar (str, unicode, int), a dict
    (mapping XML tags to whatever) or a sequence of whatever.

    @param out: xmlprinter instance for XML output.
    """

    if isinstance(value, (str, unicode)):
        return out.dataElement(xml_tag, value)

    if isinstance(value, (int, float)):
        return out.dataElement(xml_tag, str(value))

    if isinstance(value, dict):
        out.startElement(xml_tag)
        for key in value:
            output_to_xml(key, value[key], out)
        out.endElement(xml_tag)
        return 

    if isinstance(value, (list, tuple, set)):
        for item in value:
            output_to_xml(xml_tag, item, out)
        return

    assert False, "Don't know how to output value %s (type %s) for tag %s" % (
        repr(value), type(value), repr(xml_tag))
# end output
    


def dict_to_stream(d, out, surrounding_tag, logger):
    """Output data block to output stream.

    The output is utf-8-encoded (this must be respected). The dict itself us
    what *_record_to_dict functions return.

    @type d: dict of basestring to sequence of dicts (of basestring to basestring)
    @param d:
      Dictionary with entity data (be it person or OU). 

    @type stream: xmlprinter instance
    @param stream:
      xmlprinter instance ready for output.
    """

    # import pprint
    # logger.debug("Outputting XML-element:\n %s", pprint.pformat(d))
    out.startElement(surrounding_tag)
    for inner_tag in d:
        for inner_dict in d[inner_tag]:
            out.startElement(inner_tag)
            for key, value in inner_dict.iteritems():
                out.dataElement(key, value)
            out.endElement(inner_tag)

    out.endElement(surrounding_tag)
# end dict_to_stream


def consume_line(producer):
    """Consume next line from the csv.

    NB! No field stripping may happen here (it's too early because of line
    continuations). Since the csv is fubar, we clip away the last empty field
    if it exists (many lines are terminated with the field separator).

    @type producer: iterable (any type yielding successive lines)
    @param producer:
      Any iterable yielding next line from input, until there are no
      more. This could be csv.reader, iter(['foo', 'bar']) -- anything that
      supports iteration protocol and yields strings.

    @rtype: pair (bool, sequence) or raises StopIteration
    @return:
      Returns a pair. The boolean tells whether the line that populated
      sequence ended with a field terminator in csv. It is important to know
      this to be able to detect line continuations. sequence is a sequence of
      basestrings each representing one data field.

      When no more input is avaiblae from producer, this function raises
      StopIteration.
    """

    for fields in producer:
        # in july 2012 SPLO added a starting line to *.csv-file
        # without letting us know in advance. this first line contains
        # a production date for the csv file. we might in the future
        # use the production date in the xml-file as well but for now
        # we are hoping that SPLO will be able to deliver an XML-file
        # in stead. we thus strip the offending line before the file
        # is processed. Jazz, 2012-08-10
        if re.match('^#.*', fields[0]):
            continue
        ended_with_delimiter = False
        if fields[-1] == '':
            ended_with_delimiter = True
            fields.pop()
        yield ended_with_delimiter, [unicode(x, INPUT_ENCODING)
                                     for x in fields]
# end consume_line


def fields_start_record(fields, markers):
    """Decide whether a sequence of fields can be a valid input line.

    Each line starts with an L{INDENTATION} characters indent prefix that we
    ignore (it may contains something else than whitespace). The very first
    field decides if what we are looking for is a valid entry.

    @type fields: sequence of str
    @param fields:
      Fields that were extracted from a line.

    @type markers: sequence of strings
    @param markers:
      A sequence specifying valid (sub)record start markers. They may be
      several entries.

    @rtype: bool
    @return:
      Whether current sequence of fields consitutes a valid input line (rather
      than junk).
    """

    assert isinstance(fields, (list, tuple, set))
    ffield = fields[0]
    assert isinstance(ffield, basestring)
    if len(ffield) < INDENTATION:
        return False
    ffield = ffield[INDENTATION:].strip()
    return ffield in markers
# end fields_start_record


def stream_to_fields(stream, markers):
    """Yield a set of fields for each call, until no more are available.

    It's useful to think of CSV as a stream of fields (of the same type),
    without any line continuation crap to worry about. This function
    accomplishes just that. If we have a sequence of fields split over several
    lines, this function will join the multiple lines together and return one
    sequence with all the fields.

    @type stream: open file-like object
    @param stream:
      Source file to read data from. It can be any file-like object.

    @type markers: sequence of strings
    @param markers:
      A sequence specifying valid record and subrecord start markers. There
      may be several entries.

    @rtype: generator (of successive sequences of basestrings)
    @return:
      A generator suitable for iterating of sequences of fields. This function
      will raise StopIteration when no more data is available.
    """

    def strip_accumulator(accumulator):
        tmp_acc = list()
        if accumulator:
            accumulator[0] = accumulator[0][INDENTATION:]

        for x in accumulator:
            x = x.strip()
            if x == u"no_val":
                x = u""
            tmp_acc.append(x)
        
        return tmp_acc
    # end 

    reader = csv.reader(stream, delimiter=DELIMITER, quoting=csv.QUOTE_NONE)
    accumulator = list()
    acc_on_boundary = True
    for exact_ending, fields in consume_line(reader):
        # When a new (sub)record marker is detected ... 
        if fields_start_record(fields, markers):
            # ... if we have something in the accumulator
            if accumulator:
                # ... then we return it
                yield strip_accumulator(accumulator)

            # ... and in all cases we start a new accumulator
            accumulator = fields
            acc_on_boundary = exact_ending
        # ... no (sub)record marker => line continuation.
        else:
            # Accumulator CANNOT be empty at this point
            assert accumulator

            # if accumulator ended on a delimiter, no splicing magic is needed
            if acc_on_boundary:
                accumulator.extend(fields)
            # otherwise we need to adjust the last field in the accumulator,
            # since its continuation is the first field of 'fields'
            else:
                accumulator[-1] = accumulator[-1] + fields[0][INDENTATION:]
                accumulator.extend(fields[1:])

            acc_on_boundary = exact_ending

    # the final record that we cannot report until we've reached end-of-input
    assert acc_on_boundary
    yield strip_accumulator(accumulator)
# end stream_to_fields


def stream_to_records(stream, start_marker, valid_subrecord_markers,
                      all_markers):
    """Return a sequence of items representing logical records in stream.

    Each item is a sequence of fields. This way we can iterate over things of
    interest (people and OUs) without worrying too much about how they are
    laid out in the file.

    This is the next abstraction in a row:
      consume_line -> stream_to_fields -> stream_to_items.

    @type stream: open file-like object
    @param stream:
      Source file to read data from. It can be any file-like object (any
      iterable yielding strings, actually).

    @type start_marker: basestring
    @param start_marker:
      ... is a string that marks when the next **interesting** record
      starts. This is the marker separating logically distinct records of
      interest (people or OUs).

    @type valid_subrecord_markers: sequence of basestrings
    @param valid_subrecord_markers:
      This sequence lists markers that are allowed within each record.

    @type all_markers: sequence of basestrings
    @param all_markers:
      This sequences lists all valid record and subrecord markers (since
      records of different types are in the file, we cannot base record
      collecting on L{start_marker} only)

    @rtype: generator (of successive sequences of fields)
    @return:
      A generator yielding next logical record of interest (person or
      OU). Each record is a sequence of sequences with fields. It is the
      caller's responsibility to check that each sequence with fields contains
      sensible data.
    """

    assert start_marker in all_markers

    def field_starts_record(field, *markers):
        for start_marker in markers:
            if (start_marker == field.strip() or
                start_marker == field[1:].strip()):
                return True

        return False
    # end field_starts_record

    def enter_new_record(fields, in_record, accumulator):
        if not in_record:
            if field_starts_record(fields[0], start_marker):
                accumulator.append(fields)
                return True
        return False
    # end enter_new_record

    accumulator = list()
    # whether we are processing an interesting record
    in_record = False
    for fields in stream_to_fields(stream, all_markers):
        # we are starting a new record ...
        if not in_record:
            in_record = enter_new_record(fields, in_record, accumulator)
        # we are continuing current record (in the accumulator)
        else:
            # new subrecord within current record...
            if fields[0] in valid_subrecord_markers:
                accumulator.append(fields)
            # ... or next record (*ANY* record, not just start_marker-ed one)
            # - return accumulated record and reset counters
            elif field_starts_record(fields[0], *all_markers):
                yield accumulator
                accumulator = list()
                in_record = enter_new_record(fields, False, accumulator)
            # this state is impossible, but we want to trap it if we get here
            else:
                raise ValueError("Inappropriate line: <%s> in record <%s>" %
                                 (str(fields), start_marker))
            
    # the very last record on file
    if accumulator and field_starts_record(accumulator[0][0], start_marker):
        yield accumulator
# end stream_to_records



def fields_to_language(fields, offset):
    """Convert a section of the fields into language information.

    Some of the entries have language data associated with them. We don't know
    up front how many languages there'll be, so we just try to interpret
    everything that remains in this fashion. 
    """

    # Make sure that what remains are pairs "lang;value"
    if (len(fields) - offset) % 2 != 0:
        raise ValueError("Odd number of fields when extracting languages. "
                         "fields=%s, offset=%s (field=%s)" %
                         (fields, offset, fields[offset]))

    result = list()
    for index in range(offset, len(fields), 2):
        # ISO-639-1 are all 2 letter codes
        assert len(fields[index]) == 2

        # Throw away empty titles
        if not fields[index+1].strip():
            continue
        
        result.append({u"Sap_navn_spraak": fields[index],
                       u"Navn": fields[index+1]})

    return result
# end fields_to_language


def fields_to_person(fields):
    """Convert a specific subrecord to a person dictionary

    @type fields: sequence of basestring
    @param fields:
      Fields that we are interested it. fields[0] must be 'PERSON_INFO' or
      '*PERSON_INFO'. The rest could be anything.
    """

    valid_tags = (u"PERSON_INFO", u"*PERSON_INFO")
    valid_fields = (u"Fornavn", u"Etternavn", u"Mellomnavn", u"Ansattnr", 
                    u"Fodselsnummer", u"Fodselsdato", u"Kjonn", u"Nasjonalitet",
                    u"Komm.spraak", )
    collection = collector(fields[:len(valid_fields)+1], valid_tags,
                           valid_fields, {})
    assert len(collection) == 1
    assert len(collection[0]) == len(valid_fields)
    titles = fields_to_language(fields, len(valid_fields)+1)
    if titles:
        collection[0][u"Tittel"] = titles
    return collection
# end fields_to_person


def fields_to_role(fields):
    valid_tags = u"PERSON_ROLLS"
    valid_fields = (u"Rolleid", u"Stedkode", u"Start_Date", u"End_Date",)
    legal_values = {
        u"Rolleid": (u"ASSOSIERT", u"BILAGSLØNN", u"EF-FORSKER",
                     u"EF-STIP", u"EKST-KONS", u"EKST-PART",
                     u"EMERITUS", u"GJ-FORSKER", u"GRP-LÆRER", 
                     u"POLS-ANSAT", u"STEDOPPLYS", u"INNKJØPER",
                     u"PCVAKT",),
        }
    return collector(fields, valid_tags, valid_fields, legal_values)
# end fields_to_role


def fields_to_hovedstilling(fields):
    valid_tags = u"PERSON_HOVEDSTILLING"
    valid_fields = (u"adm_forsk",
                    u"DBH-KAT",
                    u"stillingsprosent",
                    u"MGType",
                    u"MUGType",
                    u"Start_Date",
                    u"End_Date",
                    u"Orgenhet",
                    u"Stillnum",
                    u"Status",
                    u"Arsak",
                    u"stillingsgruppebetegnelse",)

    collection = collector(fields[:len(valid_fields)+1], valid_tags, valid_fields, {})
    titles = fields_to_language(fields, len(valid_fields)+1)
    if titles:
        collection[0][u"Tittel"] = titles
    return collection
# end fields_to_hovedstilling


def fields_to_comm(fields):
    valid_tags = u"PERSON_COMM"
    valid_fields = (u"KOMMTYPE", u"KommVal",)
    legal_values = {
        u"KOMMTYPE":
        (u"Arbeidstelefon 1",
         u"Arbeidstelefon 2",
         u"Arbeidstelefon 3",
         u"Brukernavn i SAP-systemet (SY-UNAME)",
         u"E-post, arbeid",
         u"E-post, privat",
         u"Faks arbeid",
         u"Faks privat",
         u"Mobilnummer, jobb internt",
         u"Mobilnummer, jobb",
         u"Mobilnummer, privat",
         u"Privat e-postadresse",
         u"Privat telefon",
         u"Privat telefon, midlertidig arbeidssted",
         u"Privat mobil synlig på web",
         u"Sentralbord",
         u"Sted for lønnslipp",
         u"Svarsted",
         u"TEKSTTELEFON",
         u"TEKSTTELEFON PRIVAT",
         u"Telefaks midlertidig arbeidssted",
         u"Telefon, midlertidig arbeidssted 1",
         u"UREG UNIX Brukernavn",
         u"URL",
         )
    }
    
    return collector(fields, valid_tags, valid_fields, legal_values)
# end fields_to_comm


def fields_to_bistilling(fields):
    valid_tags = u"PERSON_BISTILLING"

    def sequence_split(seq, delimiter):
        first = True
        result = list()
        for item in seq:
            if item != delimiter:
                result.append(item)
                first = False
            else:
                if not first:
                    yield result
                first = False
                result = [delimiter,]
        yield result
    # sequence_split

    valid_fields = (u"adm_forsk",
                    u"DBH-KAT",
                    u"stillingsprosent",
                    u"MGType",
                    u"Start_Date",
                    u"End_Date",
                    u"Orgenhet",
                    u"Stillnum",
                    u"Status",
                    u"stillingsgruppebetegnelse",)

    # Since we have an unknown number of languages following each bistilling, We
    # may have multiple BISTILLING entries per line (i.e. multiple BISTILLING in
    # L{fields}). Here, we'd have to use "PERSON_BISTILLING"-element as a
    # delimiter, and only then collect title language data.
    collection = list()
    for sequence in sequence_split(fields, "PERSON_BISTILLING"):
        tmp = collector(sequence[:len(valid_fields)+1], valid_tags, valid_fields, {})
        titles = fields_to_language(sequence, len(valid_fields)+1)
        if titles:
            tmp[0][u"Tittel"] = titles
        collection.append(tmp)

    return collection
# end fields_to_bistilling


def fields_to_address(fields):
    valid_tags = u"PERSON_ADDRESS"
    valid_fields = (u"AdressType",
                    u"CO",
                    u"Gateadresse",
                    u"Adressetillegg",
                    u"Postnummer",
                    u"Poststed",
                    u"Landkode",
                    u"Reservert",)

    return collector(fields, valid_tags, valid_fields, {})
# end fields_to_address


def person_subrecord_to_item(subrecord):
    """Convert a subrecord to something suitable for output.

    @type subrecord: sequence of basestrings
    @param subrecord:
      An entry from source corresponding to one subrecord type for out person
      records. Such an entry is a sequence of basestrings. The meaning/content
      of the sequence is dependent on the type of the subrecord. Its first
      item determines the type.

    @rtype: a pair -- key (basestring), value (basestring)
    @return:
      An entry suitable for stuffing into a dictionary. The value is a
      sequence of dicts representing person data in the subrecord.
    """

    subrecord_type = subrecord[0]
    dispatch = {
        u"PERSON_ADDRESS": (u"Adresse", fields_to_address),
        u"PERSON_BISTILLING": (u"Bistilling", fields_to_bistilling),
        u"PERSON_COMM": (u"PersonKomm", fields_to_comm),
        u"PERSON_HOVEDSTILLING": (u"HovedStilling", fields_to_hovedstilling),
        u"PERSON_ROLLS": (u"Roller", fields_to_role),
        u"PERSON_INFO": (u"person", fields_to_person),
        u"*PERSON_INFO": (u"person", fields_to_person),
    }
    
    if subrecord_type not in dispatch:
        raise ValueError("Unknown subrecord for person: %s" % subrecord_type)

    entry = dispatch[subrecord_type]
    return entry[0], entry[1](subrecord)
# end person_subrecord_to_item


def person_record_to_dict(record):
    """Convert a complete record with person info to a data structure suitable
    for XML output.

    @type record: sequence of sequence of strings
    @param record:
      All info pertaining to one person. It is a sequence of sequences of
      strings. Each subsequence represents a sequence of subrecords of a
      certain type. Several subsequences may represent a subrecord of the same
      type (i.e. there may be several PERSON_COMM subrecords).

    @rtype: dict of string to list of dicts (of basestring to basestring)
    @return:
      A dictionary where they keys are the names of XML-attributes and the
      values are lists of CDATA/text values of the aforementioned
      attributes. I.e.::

        ['FOO', 'bar', 'baz']

      ... is mangled to::

        {'SOMETHING': [{'bar_key': 'bar',
                        'baz_key': 'baz'},]}

      The 'unknowns' here (SOMETHING, *_key) are determined by helper
      functions (they are essentially defined by 'FOO').
    """

    result = dict()
    for subrecord in record:
        key, item = person_subrecord_to_item(subrecord)
        result.setdefault(key, list()).extend(item)

    return result
# end person_record_to_dict


def guess_person_id_for_debug(record):
    """Extract a perosn id suitable for logging output

    To make human-friendly errors/debug messages, we don't want to output an
    entire person record. This functions extracts the juicy bits and returns a
    string that uniquely ids a person from the record specified.
    """

    for subrecord in record:
        if not subrecord:
            continue
        if u"PERSON_INFO" not in subrecord[0]:
            continue

        names = " ".join(subrecord[1:4]).strip()
        sap_id = subrecord[4]
        fnr = subrecord[6]

        return "%s (sap=%s, fnr=%s)" % (names, sap_id, fnr)

    return repr(record)
# end guess_person_id_for_debug


def guess_ou_id_for_debug(record):
    """Extract an OU id suitable for logging output"""

    for subrecord in record:
        if not subrecord:
            continue

        if u"STED_STEDKODE" not in subrecord[0]:
            continue

        sko = subrecord[0]
        return repr(record)

    return repr(record)
# end guess_ou_id_for_debug


def process_people(in_stream, out_stream, logger):
    """Consume people from file and output the corresponding XML.

    @type in_stream: open file-like object
    @param in_stream:
      Source file to read data from. It can be any file-like object (any
      iterable yielding strings, actually).

    @type out_stream: open file-like object
    @param out_stream:
      Destination file to write output to. It can be any file-like object that
      accepts write().

    @type logger: Factory.get_logger(<...>) object
    @param logger:
      Logger instance (we need warnings about failing conversions)
    """

    start_marker = u"PERSON_INFO"
    submarkers = valid_person_content
    all_valid = valid_person_content + valid_ou_content + valid_record_markers
    valid_counter = 0
    counter = 0
    for counter, record in enumerate(stream_to_records(in_stream, start_marker,
                                                       submarkers, all_valid)):
        try:
            output = person_record_to_dict(record)
            valid_counter += 1
        except:
            # NB! It ought to be a warn, but there are too many of them.
            logger.info("Failed to process person %s. "
                        "Person is skipped from output",
                        guess_person_id_for_debug(record))

            exc_t, exc_v, exc_tb = sys.exc_info()
            logger.exception("Current exception: type=%s/value=%s", exc_t, exc_v)
            continue
        
        # dict_to_stream(output, out_stream, u"sap_basPerson", logger)
        output_to_xml(u"sap_basPerson", output, out_stream)

    logger.debug("Read %d people record(s), %d valid", counter+1, valid_counter)
# end process_people



def process_OUs(in_stream, out_stream, logger):
    """Consume OUs from file and output the corresponding XML:

    @type in_stream: open file-like object
    @param in_stream:
      Source file to read data from. It can be any file-like object (any
      iterable yielding strings, actually).

    @type out_stream: open file-like object
    @param out_stream:
      Destination file to write output to. It can be any file-like object that
      accepts write().

    @type logger: Factory.get_logger(<...>) object
    @param logger:
      Logger instance (we need warnings about failing conversions)
    """

    start_marker = u"STED_STEDKODE"
    submarkers = valid_ou_content
    all_valid = valid_person_content + valid_ou_content + valid_record_markers
    valid_counter = 0
    counter = 0
    for counter, record in enumerate(stream_to_records(in_stream, start_marker,
                                                       submarkers, all_valid)):
        try:
            output = ou_record_to_dict(record)
            valid_counter += 1
        except:
            # Yeah, it ought to be an error.
            logger.info("Failed to process ou records: %s."
                        "OU is skipped", guess_ou_id_for_debug(record))
            exc_t, exc_v, exc_tb = sys.exc_info()
            logger.info("Current exception: type=%s/value=%s", exc_t, exc_v)
            continue
        
        dict_to_stream(output, out_stream, u"sap2bas_skode", logger)

    logger.debug("Read %d OU record(s), %d valid", counter+1, valid_counter)
# end process_ou


def ou_record_to_dict(record):
    """Convert a complete record with ou info to a data structure suitable
    for XML output.

    @type record: sequence of sequence of strings
    @param record:
      All info pertaining to one ou. It is a sequence of sequences of
      strings. Each subsequence represents a sequence of subrecords of a
      certain type. Several subsequences may represent a subrecord of the same
      type (i.e. there may be several STED_STEDKOMM subrecords).

    @rtype: dict of string to list of dicts (of basestring to basestring)
    @return:
      A dictionary where they keys are the names of XML-attributes and the
      values are lists of CDATA/text values of the aforementioned
      attributes. I.e.::

        ['FOO', 'bar', 'baz']

      ... is mangled to::

        {'SOMETHING': [{'bar_key': 'bar',
                        'baz_key': 'baz'},]}

      The 'unknowns' here (SOMETHING, *_key) are determined by helper
      functions (they are essentially defined by 'FOO').
    """

    result = dict()
    for subrecord in record:
        key, item = ou_subrecord_to_item(subrecord)
        result.setdefault(key, list()).extend(item)

    return result
# end ou_record_to_dict


def ou_subrecord_to_item(subrecord):
    """Convert an OU subrecord to something suitable for output.

    @type subrecord: sequence of basestrings
    @param subrecord:
      An entry from source corresponding to one subrecord type for our OU
      records. Such an entry is a sequence of basestrings. The meaning/content
      of the sequence is dependent on the type of the subrecord. Its first
      item determines the type.

    @rtype: a pair -- key (basestring), value (basestring)
    @return:
      An entry suitable for stuffing into a dictionary. The value is a
      sequence of dicts representing person data in the subrecord.
    """

    subrecord_type = subrecord[0]
    dispatch = {
        u"STED_STEDKODE": (u"stedkode", fields_to_ou),
        u"*STED_STEDKODE": (u"stedkode", fields_to_ou),
        u"STED_STEDNAVN0": (u"stednavn", fields_to_ou_name),
        u"STED_STEDADDRESS": (u"stedadresse", fields_to_ou_address),
        u"STED_STEDKOMM0": (u"stedkomm", fields_to_ou_comm),
        u"STED_STEDBRUK0": (u"stedbruk", fields_to_ou_usage),
    }
        
    if subrecord_type not in dispatch:
        raise ValueError("Unknown subrecord for ou: %s" % subrecord_type)

    entry = dispatch[subrecord_type]
    return entry[0], entry[1](subrecord)
# end ou_subrecord_to_item


def fields_to_ou(fields):
    """Convert a specific subrecord to an OU dictionary"""
    valid_tags = (u"STED_STEDKODE", u"*STED_STEDKODE")
    valid_fields = (u"Stedkode", u"Start_Date", u"End_Date", u"Overordnetsted",)
    collection = collector(fields, valid_tags, valid_fields, {})
    assert len(collection) == 1
    assert len(collection[0]) == len(valid_fields)
    return collection
# end fields_to_ou


def fields_to_ou_name(fields):
    """Convert a specific subrecord to an OU name dictionary sequence"""
    valid_tags = u"STED_STEDNAVN"
    valid_fields = (u"Sap_navn_spraak",
                    u"Akronym",
                    u"Kortnavn",
                    u"Kortnavn40",
                    u"Langnavn",)
    collection = collector(fields, valid_tags, valid_fields, {})
    return collection
# end fields_to_ou_name


def fields_to_ou_address(fields):
    """Convert a specific subrecord to an OU address dictionary sequence"""    
    valid_tags = u"STED_STEDADDRESS"
    valid_fields = (u"AdressType",
                    u"Cnavn",
                    u"Gatenavn1",
                    u"Gatenavn2",
                    u"Postnummer",
                    u"Poststed",
                    u"Landkode",
                    u"Distribusjon",)
    collection = collector(fields, valid_tags, valid_fields, {})
    return collection
# end fields_to_ou_address


def fields_to_ou_comm(fields):
    """Convert a specific subrecord to an OU comm info dictionary sequence"""

    valid_tags = u"STED_STEDKOMM"
    valid_fields = ("Stedknavn", "Stedprio", "Stedkomm",)
    collection = collector(fields, valid_tags, valid_fields, {})
    return collection
# end fields_to_ou_comm


def fields_to_ou_usage(fields):
    """Convert a specific subrecord to an OU usage info dictionary sequence"""

    valid_tags = u"STED_STEDBRUK"
    valid_fields = (u"StedType", u"StedLevel", u"StedVal",)
    collection = collector(fields, valid_tags, valid_fields, {})
    return collection
# end fields_to_ou_usage


def open_file(name):
    import zipfile
    try:
        zf = zipfile.ZipFile(name)
        infolist = zf.infolist()
        if len(infolist) != 1:
            raise RuntimeError("Too many files in zip source: %d files" %
                               len(infolist))
        zi = infolist[0]
        return zf.open(zi.filename, "r")
    except zipfile.BadZipfile:
        return open(name, "rb")
# end open_file    


def process_file(in_name, out_name, logger):
    logger.debug("Converting csv file <%s> in %s to XML <%s> in %s",
                 in_name, INPUT_ENCODING, out_name, OUTPUT_ENCODING)
    ostream = SimilarSizeWriter(out_name, "w")
    ostream.set_size_change_limit(OUTPUT_SIZE_DELTA)
    out = xmlprinter.xmlprinter(ostream,
                                indent_level=2,
                                data_mode=True,
                                # NB! must match script's encoding
                                input_encoding="utf-8")
    out.startDocument(encoding=OUTPUT_ENCODING)
    out.startElement("sap_basPerson_Data",
                     {"xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance"})
    process_people(open_file(in_name), out, logger)
    process_OUs(open_file(in_name), out, logger)

    out.endElement("sap_basPerson_Data")
    out.endDocument()
    ostream.close()
    logger.debug("Conversion complete")
# end process_file

def usage(exitcode=0):
    print __doc__
    print """Usage: sap-csv2xml.py -f FROMFILE -t TOFILE

    -f --from IMPORTFILE    The CSV file to read from.

    -t --to EXPORTFILE      The XML file to write to. 

    -h --help               Show this and quit.
    """
    sys.exit(exitcode)

def main():
    logger = Factory.get_logger("cronjob")
    try:
        options, junk = getopt.getopt(sys.argv[1:], "f:t:", ("from=", "to=",))
    except getopt.GetoptError, e:
        print e
        usage(1)

    from_file = None
    to_file = None
    for option, value in options:
        if option in ('-h', '--help'):
            usage()
        if option in ("-f", "--from",):
            from_file = value
        elif option in ("-t", "--to",):
            to_file = value

    if not from_file and to_file:
        print "Missing from or to file"
        usage(1)

    try:
        process_file(from_file, to_file, logger)
    except AssertionError:
        tp, value, tb = sys.exc_info()
        logger.error("Failed assertion: %s %s %s", tp, value, tb)
        raise
# end main


if __name__ == "__main__":
    main()

    

########################################################################
## nosetest/py.test code
##
## nose:    nosetests -s -v csv2xml-tng.py
## py.test: py.test -v csv2xml-tng.py
##
########################################################################
#
# FIXME: a few failing tests -- what if there is just some junk without record
# markers?
#
class null_logger(object):
    """No-op logger for testing purposes"""
    def debug(self, *rest, **kw):
        pass
    def warn(self, *rest, **kw):
        pass
# end null_logger
    

def test_consume_line_retval():
    """Check that consume_line returns a generator"""

    assert isinstance(consume_line(iter(list())),
                      types.GeneratorType)
# end test_consume_line_retval
   

def test_consume_line():
    """Check that consume_line stops immediately with empty input"""

    try:
        consume_line(iter(list())).next()
        # Should not be reached
        raise RuntimeError("NOTREACHED")
    except StopIteration:
        pass
# end test_consume_line


def test_consume_line2():
    """Check that consume_line parses 1 line correctly"""

    delimiter = ";"
    fields = ["foo", "bar", "baz"]
    end_delim, result = consume_line(csv.reader([delimiter.join(fields)],
                                                delimiter=delimiter,
                                                quoting=csv.QUOTE_NONE)).next()
    assert end_delim == False
    assert result == fields
# end test_consume_line2


def test_consume_line3():
    """Check that consume_line parses a delimited-terminated line correctly."""

    delimiter = ";"
    fields = ["foo", "bar", "baz"]
    end_delim, result = consume_line(
                            csv.reader([delimiter.join(fields) + delimiter],
                                       delimiter=delimiter,
                                       quoting=csv.QUOTE_NONE)).next()
    assert end_delim == True
    assert result == fields
# end test_consume_line3


def test_consume_line4():
    """Check that consume_line handles multiple calls on the same source."""

    delimiter = ";"
    fields = ["foo", "bar", "baz"]
    line = delimiter.join(fields)
    source = [line, line]
    producer = csv.reader(source, delimiter=delimiter, quoting=csv.QUOTE_NONE)
    for end_delim, result in consume_line(producer):
        assert end_delim == False
        assert result == fields
# end test_consume_line4


def test_fields_start_record1():
    """Check that all valid person/OU/record markers are detected"""
    
    indent = " "*INDENTATION
    all_valid = (valid_record_markers + valid_ou_content + valid_person_content)
    for marker in all_valid:
        assert fields_start_record([indent+marker], all_valid)
# end test_fields_start_record1


def test_fields_start_record2a():
    """Check that empty fields cannot start a record"""

    assert not fields_start_record([""], ("PERSON_INFO",))
# end test_fields_start_record2a


def test_fields_start_record3():
    """Check that fields_start_record does not accept short fields"""

    # A field cannot be a substring of marker and mark the start of a record
    assert not fields_start_record(["FOO", "bar", "baz"], ("FOOBAR",))
# end test_fields_start_record3


def test_stream_to_fields1():
    """Check that stream_to_fields barfs when no delimiter is at the end"""
    
    indent = " "*INDENTATION
    marker = "PERSON_INFO"
    fields1 = [marker, "foo", "bar"]
    # error -- no delimiter at the end    
    data = indent + DELIMITER.join(fields1)
    try:
        list(stream_to_fields(IO(data), (marker,)))
        raise ValueError("NOTREACHED")
    except AssertionError:
        pass
# end test_stream_to_fields1
    
def test_stream_to_fields2():
    """Check that stream_to_fields handles one-line record"""

    indent = " "*INDENTATION
    marker = "PERSON_INFO"
    fields1 = [marker, "foo", "bar"]
    data = indent + DELIMITER.join(fields1) + DELIMITER
    list(stream_to_fields(IO(data), (marker,)))
# end test_stream_to_fields2


def test_stream_to_fields2a():
    """Check that stream_to_fields handles non-space indent"""

    # some markers are prefixed with digits
    indent = "x"*INDENTATION
    marker = "PERSON_INFO"
    fields1 = [marker, "foo", "bar"]
    data = indent + DELIMITER.join(fields1) + DELIMITER
    list(stream_to_fields(IO(data), (marker,)))
# end test_stream_to_fields2a


def test_stream_to_fields2b():
    """Check that stream_to_fields strips non-space indent"""

    # some markers are prefixed with digits
    indent = "x"*INDENTATION
    marker = "PERSON_INFO"
    fields1 = [marker, "foo", "bar"]
    data = indent + DELIMITER.join(fields1) + DELIMITER
    d = list(stream_to_fields(IO(data), (marker,)))
    assert len(d) == 1
    d = d[0]
    assert d == fields1
# end test_stream_to_fields2b


def test_stream_to_fields3():
    """Check that line continuation with terminator at the eol works"""

    indent = " "*INDENTATION
    marker = "PERSON_INFO"
    fields1 = [marker, "foo", "bar"]
    fields2 = ["baz", "zot"]
    data = (indent + DELIMITER.join(fields1) + DELIMITER + "\n" +
            indent + DELIMITER.join(fields2) + DELIMITER)
    x = stream_to_fields(IO(data), (marker,)).next()
    assert x == fields1 + fields2
# end test_stream_to_fields3

def test_stream_to_fields4():
    """Check that line continuation without terminator at the eol works"""

    indent = " "*INDENTATION
    marker = "PERSON_INFO"
    fields1 = [marker, "foo", "bar"]
    fields2 = ["baz", "zot"]
    data = (indent + DELIMITER.join(fields1) + "\n" +
            indent + DELIMITER.join(fields2) + DELIMITER)
    x = stream_to_fields(IO(data), (marker,)).next()
    assert x == fields1[:-1] + [fields1[-1]+fields2[0],] + fields2[1:]
# end test_stream_to_fields4


def test_stream_to_fields4b():
    """Check that line continuation over multiple lines work"""

    indent = " "*INDENTATION
    marker = "PERSON_INFO"
    fields1 = [marker, "foo", "bar"]
    fields2 = ["baz", "zot"]
    fields3 = ["qux", "quux"]
    data = (indent + DELIMITER.join(fields1) + "\n" +
            indent + DELIMITER.join(fields2) + "\n" +
            indent + DELIMITER.join(fields3) + DELIMITER)
    x = stream_to_fields(IO(data), (marker,)).next()
    assert x == (fields1[:-1] + [fields1[-1]+fields2[0],] +
                 fields2[1:-1] + [fields2[-1]+fields3[0],] +
                 fields3[1:])
# end test_stream_to_fields4


def test_stream_to_fields5():
    """Check that spliced lines preserve whitespace"""

    indent = " "*INDENTATION
    marker = "PERSON_INFO"
    fields1 = [marker, "foo", "bar", "baz "] # <- NB! space
    fields2 = [" bar", "zot"]                # <- NB! space
    data = (indent + DELIMITER.join(fields1) + "\n" +
            indent + DELIMITER.join(fields2) + DELIMITER)
    x = stream_to_fields(IO(data), (marker,)).next()
    should_be = (fields1[:-1] +
                 [fields1[-1] + fields2[0]] +
                 fields2[1:])
    assert x == should_be
# end test_stream_to_field5

def test_stream_to_fields6():
    """Check that stream_to_fields strips indents"""

    marker = "PERSON_INFO"
    fields = [marker, "foo", "bar", "baz"]
    indent = " "*INDENTATION
    data = indent + DELIMITER.join(fields) + DELIMITER
    x = stream_to_fields(IO(data), [marker,]).next()
    assert x == fields
# end test_stream_to_fields6


def test_stream_to_fields7():
    """Check that stream_to_fields mangles no_val"""

    marker = "PERSON_INFO"
    fields = [marker, "no_val",]
    indent = " "*INDENTATION
    data = indent + DELIMITER.join(fields) + DELIMITER
    x = stream_to_fields(IO(data), [marker,]).next()
    assert len(x) == len(fields)
    assert x[0] == fields[0]
    assert x[1] == ''
# end test_stream_to_fields7

    
def test_stream_to_records1():
    """Check that a record without subrecords works"""

    marker = "PERSON_INFO"
    fields = [marker, "foo", "bar", "baz"]
    indent = " "*INDENTATION
    data = indent + DELIMITER.join(fields) + DELIMITER

    result = stream_to_records(IO(data), marker, (), (marker,)).next()
    assert len(result) == 1
    assert result[0] == fields
# end test_stream_to_records1


def test_stream_to_records2():
    """Check that 2 lines without valid markers give 0 subrecords"""

    marker = "PERSON_INFO"
    fields1 = [marker, "foo", "bar", "baz"]
    fields2 = ["JUNK", "qux1", "qux2"]
    indent = " "*INDENTATION
    data = (indent + DELIMITER.join(fields1) + DELIMITER + "\n" +
            indent + DELIMITER.join(fields2) + DELIMITER)
    x = stream_to_records(IO(data), marker, (), (marker,)).next()
    assert len(x) == 1 # <- 1 record only
    assert len(x[0]) == len(fields1) + len(fields2)
    assert x[0] == fields1 + fields2
# end test_stream_to_records2


def test_stream_to_records3():
    """Check that 1 record + 1 subrecord work"""

    marker = "PERSON_INFO"
    submarker = "JUNK"
    fields1 = [marker, "foo", "bar", "baz"]
    fields2 = [submarker, "qux1", "qux2"]
    indent = " "*INDENTATION
    data = (indent + DELIMITER.join(fields1) + DELIMITER + "\n" +
            indent + DELIMITER.join(fields2) + DELIMITER)
    x = stream_to_records(IO(data), marker, (submarker,),
                          (marker, submarker,)).next()
    assert len(x) == 2
    assert x[0] == fields1
    assert x[1] == fields2
# end test_stream_to_records3


def test_stream_to_records4():
    """Check that we collected marked records only"""

    indent = " "*INDENTATION
    marker = "PERSON_INFO"
    submarker = "FOO"
    ignore_marker = "BAR"
    fields1 = [marker, "f1", "f2"]
    fields2 = [submarker, "sf1", "sf2"]
    fields3 = [ignore_marker, "i1", "i2"]
    data = (indent + DELIMITER.join(fields1) + DELIMITER + "\n" +
            indent + DELIMITER.join(fields2) + DELIMITER + "\n" +
            indent + DELIMITER.join(fields3) + DELIMITER)
    x = list(stream_to_records(IO(data), marker, (submarker,),
                               (marker, submarker, ignore_marker)))
    assert len(x) == 1
    record = x[0]
    assert record[0] == fields1
    assert record[1] == fields2
# end test_stream_to_records4


def test_stream_to_records5():
    """Check that stream_to_records returns the last record"""

    indent = " "*INDENTATION
    marker = "PERSON_INFO"
    submarker = "FOO"
    ignore_marker = "BAR"
    fields1 = [marker, "f1", "f2"]
    fields2 = [submarker, "sf1", "sf2"]
    data = (indent + DELIMITER.join(fields1) + DELIMITER + "\n" +
            indent + DELIMITER.join(fields2) + DELIMITER)
    x = list(stream_to_records(IO(data), marker, (submarker,),
                               (marker, submarker, ignore_marker)))
    assert len(x) == 1
    record = x[0]
    assert record[0] == fields1
    assert record[1] == fields2
# end test_stream_to_records4


def test_stream_to_records6():
    """Check that 1 record + 0 subrecords with line continuation works"""
    
    indent = " "*INDENTATION
    marker = "PERSON_INFO"
    submarker = "FOO"
    fields1 = [marker, "f1", "f2"]
    fields2 = ["sf1", "sf2"]
    data = (indent + DELIMITER.join(fields1) + "\n" +
            indent + DELIMITER.join(fields2) + DELIMITER)
    x = list(stream_to_records(IO(data), marker, (submarker,),
                               (marker, submarker,)))
    assert len(x) == 1
    record = x[0]
    assert record[0] == fields1[:-1] + [fields1[-1]+fields2[0],] + fields2[1:]
# end test_stream_to_records6


def test_collecto10():
    """Check that mismatches between # of names and # of fields is signalled"""

    tag = "FOO"
    fields1 = (tag, "bar1",)
    fields2 = (tag, "bar2", "baz")
    # One name, but 2 fields in fields2 (which is the last one)
    names = ("bar_tag",)
    try:
        d = collector(fields1+fields2, tag, names, {})
        raise RuntimeError("NOTREACHED")
    except ValueError:
        pass
# end test_collector10
    

def test_collector9():
    """Check that sequences of tags are possible"""
    
    tags = ("FOO", "BAR")
    fields1 = (tags[0], "bar1",)
    fields2 = (tags[1], "bar2",)
    # One name, but 2 fields in fields2 (which is the last one)
    names = ("bar_tag",)
    d = collector(fields1+fields2, tags, names, {})
    assert len(d) == 2
    sub_d = d[0]
    assert len(sub_d) == 1
    assert sub_d[names[0]] == fields1[1]
    sub_d = d[1]
    assert len(sub_d) == 1
    assert sub_d[names[0]] == fields2[1]
# end test_collector9


def test_collector8():
    """Check that tag submatch is possible"""

    tag = "FOO"
    fields1 = (tag + "JUNK", "bar1",)  # <- FOOJUNK != FOO
    fields2 = (tag, "bar2",)
    # One name, but 2 fields in fields2 (which is the last one)
    names = ("bar_tag",)
    d = collector(fields1+fields2, tag, names, {})
    assert len(d) == 2
    sub_d = d[0]
    assert len(sub_d) == 1
    assert sub_d[names[0]] == fields1[1]
    sub_d = d[1]
    assert len(sub_d) == 1
    assert sub_d[names[0]] == fields2[1]
# end test_collector8


def test_collector7():
    """Check that even the last field set must have the proper # of fields."""

    tag = "FOO"
    fields1 = (tag, "bar1",)
    fields2 = (tag, "bar2", "baz2")
    # One name, but 2 fields in fields2 (which is the last one)
    names = ("bar_tag",)
    try:
        d = collector(fields1+fields2, tag, names, {})
        raise RuntimeError("NOTREACHED")
    except ValueError:
        pass
# end test_collector7


def test_collector6():
    """Check that that extraneous data fields fail in collector."""

    tag = "FOO"
    fields1 = (tag, "bar1", "baz1")
    fields2 = (tag, "bar2",)
    # One name, but 2 fields in fields1
    names = ("bar_tag",)
    try:
        d = collector(fields1+fields2, tag, names, {})
        raise RuntimeError("NOTREACHED")
    except ValueError:
        pass
# end test_collector6
    

def test_collector5():
    """Check that return value of collector is of proper type"""

    tag = "FOO"
    fields1 = (tag, "bar1", "baz1")
    names = ("bar_tag", "baz_tag")
    d = collector(fields1, tag, names, {})
    assert isinstance(d, (tuple, list))
    assert len(d) == 1
    sub_d = d[0]
    assert len(sub_d) == 2
    assert isinstance(sub_d, dict)
    assert sorted(sub_d.keys()) == sorted(names)
    assert sorted(sub_d.values()) == sorted(fields1[1:])
# end test_collector5

def test_collector4():
    """Check that # of items in a sequence matches # of names."""

    tag = "FOO"
    fields1 = (tag, "bar1", "baz1")
    fields2 = (tag, "bar2", "baz2")
    names = ("bar_tag", "baz_tag")
    d = collector(fields1+fields2, tag, names, {})
    for name in names:
        assert all([name in sub_d for sub_d in d])
# end test_collector4

def test_collector3():
    """Check that tag must exist somewhere between values"""

    fields = ("FOO", "bar", "baz")
    tag = "FOO-FAIL"  # <- FOO-FAIL != FOO
    names = ("bar_tag", "baz_tag")
    try:
        collector(fields, tag, names, {})
        raise RuntimeError("NOTREACHED")
    except ValueError:
        pass
# end test_collector2


def test_collector2():
    """Check that non-controlled values can exist."""
    
    fields = ("FOO", "bar", "baz")
    tag = "FOO"
    names = ("bar_tag", "baz_tag")
    # without legal_values, any value goes
    collector(fields, tag, names, {}) 
# end test_collector2


def test_collector1():
    """Check that illegal values are not allowed between tags"""

    fields = ("FOO", "bar", "baz")
    tag = "FOO"
    names = ("bar_tag", "baz_tag")
    try:
        collector(fields, tag, names, {"bar_tag": "zot"}) # <- fail
        raise RuntimeError("NOTREACHED")
    except ValueError:
        pass
# end test_collector1


def test_fields_to_person4():
    """Check that multiple person entries in a record fail"""

    fields = ("PERSON_INFO", "name1", "name2", "name3",
              "1234", "fnr", "1000-01-01", "M", "X", "no_val",
              # 2nd record must fail, we expect a language here.
              "PERSON_INFO", "name1", "name2", "name3",
              "1234", "fnr", "1000-01-01", "M", "X", "no_val")
    try:
        result = fields_to_person(fields)
        raise RuntimeError("NOTREACHED")
    except AssertionError:
        pass
# end test_fields_to_person4


def test_fields_to_person3():
    """Check that a proper person entry works"""
    
    fields = ("PERSON_INFO", "name1", "name2", "name3",
              "1234", "fnr", "1000-01-01", "M", "X", "no_val")
    result = fields_to_person(fields)
    assert len(result) == 1
    p = result[0]
    assert all([v in fields for v in p.values()])
# end test_fields_to_person3


def test_fields_to_person2():
    """Check that a person entry has the right number of fields"""
    
    fields = ("PERSON_INFO", "foo", "bar")
    try:
        fields_to_person(fields)
        raise RuntimeError("NOTREACHED")
    except ValueError:
        pass
# end test_fields_to_person2


def test_fields_to_person1():
    """Check that non-person tag results in failure"""

    try:
        fields_to_person(("foo", "bar", "baz"))
        raise RuntimeError("NOTREACHED")
    except ValueError:
        pass
# end test_fields_to_person1


def test_fields_to_role4():
    """Check that an illegal role id results in failure"""
    
    fields = (u"PERSON_ROLLS", u"BILAGSLØNN", u"1234", u"2009-01-01", u"no_val",
              # schnappi is illegal here
              u"PERSON_ROLLS", u"schnappi", u"1234", u"1000-01-01", u"2009-01-01")
    try:
        fields_to_role(fields)
    except ValueError:
        pass
# end test_fields_to_role4
    

def test_fields_to_role3():
    """Check that a proper role entry works"""
    
    fields = (u"PERSON_ROLLS", u"BILAGSLØNN", u"1234", u"2009-01-01", u"no_val",
              u"PERSON_ROLLS", u"EMERITUS", u"1234", u"1000-01-01", u"2009-01-01")
    result = fields_to_role(fields)
    assert len(result) == 2
    for sub_r in result:
        assert all([v in fields for v in sub_r.values()])
# end test_fields_to_person3


def test_fields_to_role2():
    """Check that a role entry has the right number of fields"""
    
    fields = ("PERSON_ROLLS", "EMERITUS", "1000-01-01", "2009-01-01")
    try:
        fields_to_role(fields)
        raise RuntimeError("NOTREACHED")
    except ValueError:
        pass
# end test_fields_to_role2


def test_fields_to_role1():
    """Check that non-role tag results in failure"""

    try:
        fields_to_role(("foo", "bar", "baz"))
        raise RuntimeError("NOTREACHED")
    except ValueError:
        pass
# end test_fields_to_role1


def test_fields_to_hovedstilling3():
    """Check that a proper hovedstilling entry works"""
    
    fields = ("PERSON_HOVEDSTILLING", "øæå", "1234", "bla", "no_val1",
              "no_val2", "no_val3", "no_val4", "no_val5", "no_val6",
              "no_val7", "no_val8",)

    result = fields_to_hovedstilling(fields)
    assert len(result) == 1
    for sub_r in result:
        assert all([v in fields for v in sub_r.values()])
# end test_fields_to_hovedstilling3


def test_fields_to_hovedstilling2():
    """Check that a hovedstilling entry has the right number of fields"""
    
    fields = ("PERSON_HOVEDSTILLING",
              "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11",)
    fields_to_hovedstilling(fields)
# end test_fields_to_hovedstilling2


def test_fields_to_hovedstilling4():
    """Check that a hovedstilling entry supports languages"""

    fields = ("PERSON_HOVEDSTILLING",
              "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "NB", "title1")
    collection = fields_to_hovedstilling(fields)
    assert "Tittel" in collection[0]
# end test_fields_to_hovedstilling3


def test_fields_to_hovedstilling1():
    """Check that non-hovedstilling tag results in failure"""

    try:
        fields_to_hovedstilling(("foo", "bar", "baz"))
        raise RuntimeError("NOTREACHED")
    except ValueError:
        pass
# end test_fields_to_hovedstilling1


def test_fields_to_comm4():
    """Check that an illegal KOMMTYPE fails"""
    
    fields = ("PERSON_COMM", "Arbeidstelefon 1", "1234",
              "PERSON_COMM", "ERRORERROR", "1234")
    try:
        fields_to_comm(fields)
        raise RuntimeError("NOTREACHED")
    except ValueError:
        pass
# end test_fields_to_comm4


def test_fields_to_comm3():
    """Check that a proper comm entry works"""
    
    fields = ("PERSON_COMM", "Arbeidstelefon 1", "1234",
              "PERSON_COMM", "Faks arbeid", "1234")
    result = fields_to_comm(fields)
    assert len(result) == 2
    for sub_r in result:
        assert all([v in fields for v in sub_r.values()])
# end test_fields_to_comm3

 
def test_fields_to_comm2():
    """Check that a comm entry has the right number of fields"""
    
    fields = ("PERSON_COMM", "Arbeidstelefon 1")
    try:
        fields_to_comm(fields)
        raise RuntimeError("NOTREACHED")
    except ValueError:
        pass
# end test_fields_to_comm2


def test_fields_to_comm():
    """Check that non-comm tag results in failure"""

    try:
        fields_to_comm(("foo", "bar", "baz"))
        raise RuntimeError("NOTREACHED")
    except ValueError:
        pass
# end test_fields_to_comm


def test_fields_to_language():
    """Check that we don't use empty language codes"""

    fields = ("", "foo")
    try:
        fields_to_language(fields, 0)
    except AssertionError:
        pass
# end test_fields_to_language


def test_fields_to_language2():
    """Check that language codes are 2 chars wide"""

    fields = ("NOR", "foo")
    try:
        fields_to_language(fields, 0)
    except AssertionError:
        pass
# end test_fields_to_language2


def test_fields_to_language_even():
    """Assert that the REMAINDER of fields is even."""

    fields = ("NO", "NB", "NO", "EN", "FR")
    try:
        fields_to_language(fields, 0)
    except AssertionError:
        pass

    fields_to_language(fields, 1)
# end test_fields_to_language_even


def test_fields_to_bistilling3():
    """Check that a proper bistilling entry works"""
    
    fields = ("PERSON_BISTILLING", "øæå", "1234", "bla", "no_val1",
              "no_val2", "no_val3", "no_val4", "no_val5", "no_val6",
              "no_val7",)

    result = fields_to_bistilling(fields)
    assert len(result) == 1
    for sub_r in result:
        assert all(v in fields for v in sub_r.values())
# end test_fields_to_bistilling3


def test_fields_to_bistilling2():
    """Check that a bistilling entry has the right number of fields"""
    
    fields = ("PERSON_BISTILLING",
              "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",)

    fields_to_bistilling(fields)
# end test_fields_to_bistilling2


def test_fields_to_bistilling1():
    """Check that non-bistilling tag results in failure"""

    try:
        fields_to_bistilling(("foo", "bar", "baz"))
        raise RuntimeError("NOTREACHED")
    except ValueError:
        pass
# end test_fields_to_bistilling1


def test_fields_to_address3():
    """Check that a proper address entry works"""
    
    fields = ("PERSON_ADDRESS", "øæå", "1234", "bla", "no_val1",
              "no_val2", "no_val3", "no_val4", "no_val5",)

    result = fields_to_address(fields)
    assert len(result) == 1
    for sub_r in result:
        assert all([v in fields for v in sub_r.values()])
# end test_fields_to_bistilling3


def test_fields_to_address2():
    """Check that a bistilling entry has the right number of fields"""
    
    fields = ("PERSON_BISTILLING",
              "1", "2", "3", "4", "5", "6", "7",)
    try:
        fields_to_address(fields)
        raise RuntimeError("NOTREACHED")
    except ValueError:
        pass
# end test_fields_to_address2


def test_fields_to_address1():
    """Check that non-address tag results in failure"""

    try:
        fields_to_address(("foo", "bar", "baz"))
        raise RuntimeError("NOTREACHED")
    except ValueError:
        pass
# end test_fields_to_address1


def test_person_record_to_dict1():
    """Check that a valid person record is properly remapped to a dict."""

    person_record = ["PERSON_INFO", "Test", "Person", "", "", "",
                     "1950-01-01", "M", "", ""]
    role_record1 = ["PERSON_ROLLS", "ASSOSIERT", "1234", "", "",
                    "PERSON_ROLLS", "EKST-KONS", "7890", "", ""]
    role_record2 = ["PERSON_ROLLS", "EMERITUS", "5678", "", ""]
    record = [person_record, role_record1, role_record2]
    d = person_record_to_dict(record)

    # 2 keys - "person" and Roller
    assert len(d) == 2
    assert "person" in d
    assert "Roller" in d
    for value in d["person"][0].itervalues():
        assert value in person_record
    for seq in d["Roller"]:
        for value in seq.itervalues():
            assert value in role_record1 + role_record2
# end test_person_record_to_dict1


def test_process_people1():
    """Check that process_people() does a full input-output cycle"""

    marker = "PERSON_INFO"
    fields = [marker, "First", "Last", "Middle", "1234", "1234",
              "1950-01-01", "M", "no_val", "no_val"]
    indent = " "*INDENTATION
    data = indent + DELIMITER.join(fields) + DELIMITER
    stream1 = IO(data)
    stream2 = IO()
    printer = xmlprinter.xmlprinter(stream2,
                                    indent_level=2,
                                    data_mode=True,
                                    input_encoding="utf-8")
    printer.startDocument(OUTPUT_ENCODING)
    process_people(stream1, printer, null_logger())
    printer.endDocument()
    stream2.getvalue()
# end test_process_people1


def test_fields_to_ou4():
    """Check that multiple OU entries in one record fail"""
    
    fields = ("STED_STEDKODE", "foo", "bar", "baz", "zot",
              "STED_STEDKODE", "foo", "bar", "baz", "zot",)
    try:
        fields_to_ou(fields)
        raise RuntimeError("NOTREACHED")
    except AssertionError:
        pass
# end test_fields_to_ou4


def test_fields_to_ou3():
    """Check that a proper OU entry works"""
    
    fields = ("STED_STEDKODE", "foo", "bar", "baz", "zot",)
    result = fields_to_ou(fields)
    assert len(result) == 1
    ou = result[0]
    assert all([v in fields for v in ou.values()])
# end test_fields_to_ou3


def test_fields_to_ou2():
    """Check that an OU record has the right number of fields"""

    fields = ("STED_STEDKODE", "foo", "bar")
    try:
        fields_to_ou(fields)
        raise RuntimeError("NOTREACHED")
    except ValueError:
        pass
# end test_fields_to_ou2


def test_fields_to_ou1():
    """Check that non-ou tags result in failure"""

    try:
        fields_to_ou(("foo", "bar", "baz"))
        raise RuntimeError("NOTREACHED")
    except ValueError:
        pass
# end test_fields_to_ou1
    

def test_fields_to_ou_name3():
    """Check that proper ou name entries work"""
    
    fields = ("STED_STEDNAVN0", "FOO", "bar", "baz", "zot", "qux",
              "STED_STEDNAVN1", "FOO2", "bar2", "baz2", "zot2", "qux2",
              "STED_STEDNAVN2", "FOO3", "bar3", "baz3", "zot3", "qux3",)
    result = fields_to_ou_name(fields)
    assert len(result) == 3
    for sub_r in result:
        assert all([v in fields for v in sub_r.values()])
# end test_fields_to_ou3


def test_fields_to_ou_name2():
    """Check that an ou name entry has the right number of fields"""
    
    fields = ("STED_STEDNAVN0", "foo", "bar", "baz")
    try:
        fields_to_ou_name(fields)
        raise RuntimeError("NOTREACHED")
    except ValueError:
        pass
# end test_fields_to_ou_name2


def test_fields_to_ou_name1():
    """Check that non-ou name tag results in failure"""

    try:
        fields_to_ou_name(("foo", "bar", "baz"))
        raise RuntimeError("NOTREACHED")
    except ValueError:
        pass
# end test_fields_to_ou_name1


def test_fields_to_ou_address3():
    """Check that proper ou address entries work"""
    
    fields = ("STED_STEDADDRESS", "1", "2", "3", "4", "5", "6", "7", "8",
              "STED_STEDADDRESS", "a", "b", "c", "d", "e", "f", "g", "h",)
    result = fields_to_ou_address(fields)
    assert len(result) == 2
    for sub_r in result:
        assert all([v in fields for v in sub_r.values()])
# end test_fields_to_ou_address3


def test_fields_to_ou_address2():
    """Check that an ou address entry has the right number of fields"""
    
    fields = ("STED_STEDADDRESS", "foo", "bar", "baz")
    try:
        fields_to_ou_address(fields)
        raise RuntimeError("NOTREACHED")
    except ValueError:
        pass
# end test_fields_to_ou_address2


def test_fields_to_ou_address1():
    """Check that non-ou address tag results in failure"""

    try:
        fields_to_ou_address(("foo", "bar", "baz"))
        raise RuntimeError("NOTREACHED")
    except ValueError:
        pass
# end test_fields_to_ou_address1

def test_fields_to_ou_comm3():
    """Check that proper ou comm entries work"""
    
    fields = ("STED_STEDKOMM", "1", "2", "3",
              "STED_STEDKOMM", "a", "b", "c",)
    result = fields_to_ou_comm(fields)
    assert len(result) == 2
    for sub_r in result:
        assert all([v in fields for v in sub_r.values()])
# end test_fields_to_ou_comm3


def test_fields_to_ou_comm2():
    """Check that an ou comm entry has the right number of fields"""
    
    fields = ("STED_STEDKOMM", "foo",)
    try:
        fields_to_ou_comm(fields)
        raise RuntimeError("NOTREACHED")
    except ValueError:
        pass
# end test_fields_to_ou_comm2


def test_fields_to_ou_comm1():
    """Check that non-ou comm tag results in failure"""

    try:
        fields_to_ou_comm(("foo", "bar", "baz"))
        raise RuntimeError("NOTREACHED")
    except ValueError:
        pass
# end test_fields_to_ou_comm1


def test_fields_to_ou_usage3():
    """Check that proper stedbruk entries work"""
    
    fields = ("STED_STEDBRUK", "1", "2", "3",
              "STED_STEDBRUK", "a", "b", "c",)
    result = fields_to_ou_usage(fields)
    assert len(result) == 2
    for sub_r in result:
        assert all([v in fields for v in sub_r.values()])
# end test_fields_to_ou_usage3


def test_fields_to_ou_usage2():
    """Check that a 'stedbruk' entry has the right number of fields"""
    
    fields = ("STED_STEDBRUK", "foo",)
    try:
        fields_to_ou_usage(fields)
        raise RuntimeError("NOTREACHED")
    except ValueError:
        pass
# end test_fields_to_ou_usage2


def test_fields_to_ou_usage1():
    """Check that non-'ou stedbruk' tag results in failure"""

    try:
        fields_to_ou_usage(("foo", "bar", "baz"))
        raise RuntimeError("NOTREACHED")
    except ValueError:
        pass
# end test_fields_to_ou_usage1


def test_ou_record_to_dict1():
    """Check that a valid OU record is properly remapped to a dict."""

    ou_record = ["STED_STEDKODE", "one", "two", "three", "four",]
    ou_name = ["STED_STEDNAVN0", "aa", "bb", "cc", "dd", "ee"]
    ou_comm = ["STED_STEDKOMM0", "comm1", "comm2", "comm3",]
    record = [ou_record, ou_name, ou_comm]
    d = ou_record_to_dict(record)
    assert len(d) == 3
    assert "stedkode" in d
    assert "stednavn" in d
    assert "stedkomm" in d

    tmp = d["stedkode"][0]
    assert sorted(tmp.values()) == sorted(ou_record[1:])
    tmp = d["stednavn"][0]
    assert sorted(tmp.values()) == sorted(ou_name[1:])
    tmp = d["stedkomm"][0]
    assert sorted(tmp.values()) == sorted(ou_comm[1:])
# end test_ou_record_to_dict1
    

def test_process_ous1():
    """Check that process_OUs() does a full input-output cycle"""

    marker = "STED_STEDKODE"
    fields = [marker, "Foo", "Nar", "Baz", "Zot"]
    indent = " "*INDENTATION
    data = indent + DELIMITER.join(fields) + DELIMITER
    stream1 = IO(data)
    stream2 = IO()
    printer = xmlprinter.xmlprinter(stream2,
                                    indent_level=2,
                                    data_mode=True,
                                    input_encoding="utf-8")
    printer.startDocument(OUTPUT_ENCODING)
    process_OUs(stream1, printer, null_logger())
    printer.endDocument()
    stream2.getvalue()
# end test_process_ous1
