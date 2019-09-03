#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2017-2018 University of Oslo, Norway
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
""" This script exports people with partial employments, and their work titles.

We read personal work titles from sap2bas.xml and generate an LDIF that
contains persons with multiple employments, and the relevant work title for
those employments.

The employments are stored in a multivalued LDAP field,
'uioPersonPartialEmployment':

    uioPersonPartialEmployment:
    <uioPersonScopedAffiliation1>#[<lang>:<title>[;<lang>:<title>[…]]]

... where <uioPersonScopedAffiliation1> follows the format:

    (primary|secondary):<aff>[/<aff_status>]@[sko,]<root_sko>

NOTE: If you're using stdout and trying to pipe into something, you'll want to
set `PYTHONIOENCODING='utf-8'`.

"""
from __future__ import absolute_import, unicode_literals

import argparse
import logging
import os
import sys
from mx import DateTime
from contextlib import contextmanager

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.utils.funcwrap import memoize
from Cerebrum.utils.atomicfile import AtomicFileWriter
from Cerebrum.modules import LDIFutils

from Cerebrum.modules.xmlutils.system2parser import system2parser
from Cerebrum.modules.xmlutils.xml2object import DataEmployment
from Cerebrum.modules.xmlutils.xml2object import DataPerson
from Cerebrum.modules.xmlutils.xml2object import DataOU


DEFAULT_INPUT_FILE = os.path.join(cereconf.CACHE_DIR, 'SAP', 'sap2bas.xml')
DEFAULT_OUTPUT_FILE = os.path.join(cereconf.CACHE_DIR, 'LDAP',
                                   'delt_stilling.ldif')

# SAP DataEmployment.category to ANSATT/<status>
CATEGORY_TO_STATUS = {
    DataEmployment.KATEGORI_OEVRIG: 'tekadm',
    DataEmployment.KATEGORI_VITENSKAPLIG: 'vitenskapelig', }


logger = logging.getLogger(__name__)


class OrgTree(object):
    """ OU-tree lookup from DataEmployment.

    This class turns into a callable that converts the 'place' attribute of
    DataEmployment objects into a list of SKO-tuples (faculty, institute,
    department).
    """

    def __init__(self, iter_ous, include_ou=None):
        """
        :param iter_ous:
            Iterable with DataOU objects.
        :param include_ou:
            A callable that takes a DataOU object, and returns True if the ou
            should be included in a tree, or False if it should not.
        """
        # Maps <sko-tuple> -> (<parent-sko-tuple>, <show-ou>)
        self.map = dict()
        now = DateTime.now()
        include_ou = include_ou or (lambda ou: True)
        for ou in iter_ous:
            sko, parent = ou.get_id(DataOU.NO_SKO), ou.parent
            if not sko:
                continue
            if ou.start_date and ou.start_date > now:
                continue
            if ou.end_date and ou.end_date < now:
                continue
            if parent is not None:
                parent_type, parent = parent
                if not parent_type == DataOU.NO_SKO:
                    raise ValueError(
                        "Invalid parent OU type {0!r}".format(parent))

            self.map[sko] = parent, include_ou(ou)

    @memoize
    def get_nodes(self, *sko):
        try:
            parent, publishable = self.map[sko]
        except KeyError:
            raise ValueError("No ou {0}".format(sko))
        except ValueError:
            raise ValueError("Invalid ou {0}".format(sko))

        nodes = []

        if publishable:
            nodes.append(sko)

        if parent:
            # This will be an infinite loop if the OU tree contains cycles.
            nodes.extend(self.get_nodes(*parent))
        return nodes

    def __call__(self, employment):
        """ Look up OU tree from a DataEmployment.

        :param DataEmployment employment:
            The employment to fetch our OUs for.

        :return list:
            Returns a list of SKO tuples (the last tuple being the root ou).
        """
        place_type, place_id = employment.place if employment.place else (None,
                                                                          None)
        if place_type == DataOU.NO_SKO:
            return self.get_nodes(*place_id)
        return []


class AffSelector(dict):
    """
    Mapping {(aff,status): bool, (aff,): bool, ..., (): bool (default value)}.
    Corresponds to a boolean selector in Cerebrum.modules.OrgLDIF.
    """

    def __init__(self, selector):
        """
        :param dict selector:
            Typically, the `cereconf.LDAP_PERSON['affiliation_selector']`
            value.  The dict should map from a key, or key tuple to a boolean
            value, alternatively, to a new dict that maps from a key or key
            tuple to a boolean value.
        """

        self.add((), selector)
        self.setdefault((), False)

    def add(self, key_prefix, selector):
        """Normalize and add selector"""
        for key, sub_selector in selector.iteritems():
            for key in (key if isinstance(key, tuple) else (key,)):
                key = key_prefix + (key,)
                if isinstance(sub_selector, dict):
                    self.add(key, sub_selector)
                else:
                    assert isinstance(sub_selector, bool), (key, sub_selector)
                    self[key] = sub_selector

    def __missing__(self, key):
        """Find key[:-1] and cache it in self[key]"""
        ret = self[key] = self[key[:-1]]
        return ret

    def __call__(self, employment):
        """ Decide if employment could be included as partial employment. """
        if not employment.is_active():
            return False
        if employment.kind not in (DataEmployment.HOVEDSTILLING,
                                   DataEmployment.BISTILLING):
            return False
        return self["ANSATT", CATEGORY_TO_STATUS.get(employment.category,
                                                     employment.category)]


class LanguageSelector(object):
    """ Decide if a language should be included.  """

    def __init__(self, languages=None):
        """
        :param list languages:
            A list of languages to select, or `None` to select all languages.
        """
        if languages is None:
            self.languages = None
        else:
            self.languages = frozenset(languages)

    def __call__(self, language):
        """ language -> (True|False). """
        return self.languages is None or language in self.languages


class OUSelector(object):
    """ Decide if an OU should be included in formatted affiliation. """

    def __init__(self, role=None, ou_role_map=None):
        """
        :param str role:  The role (spread) to select an OU.
        :param dict ou_role_map: Mapping from 'usage code' to role (spread)
        """
        ou_role_map = ou_role_map or dict()
        self.valid_code = lambda c: role == ou_role_map.get(c)

    def __call__(self, ou):
        """ DataOU -> (True|False). """
        if not any(self.valid_code(c) for c in ou.iter_usage_codes()):
            return False
        return ou.publishable


def iterate_employments(person, selector):
    """ Iterate over active employments to consider in a Person object.

    :param SAPPerson person:
        The person to consider employments for.
    :param callable selector:
        A callable that takes a DataEmployment object, and decides if it counts
        as an employment.

    :returns generator:
        Returns a generator that iterates over valid DataEmployment objects.
    """
    seen = list()

    def is_seen(emp):
        # Make placement unique per place, to avoid duplicate entries
        # TODO: consider more than place? That's what cerebrum does, but we may
        # loose affiliation weighting here (e.g. we may get tekadm in stead of
        # vitenskaplig, if both exist at the same place).
        return any(emp.place == e.place for e in seen)

    # Two passes, to make sure we consider the main employment first.
    # Sometimes an employment is registered both as primary and secondary
    # employment...
    for e in person.iteremployment():
        if selector(e) and e.is_main():
            seen.append(e)
            yield e
            break
    for e in person.iteremployment():
        if selector(e) and not is_seen(e):
            seen.append(e)
            yield e


def iterate_employment_titles(employment):
    """ Iterate over work titles in an employment

    :param DataEmployment employment:
        The employment to consider

    :return generator:
        Returns a generator that iterates over DataName values with work
        titles.
    """
    titles = employment.get_name(DataEmployment.WORK_TITLE) or list()
    for t in titles:
        yield t


def format_employment_affiliation(employment):
    """ DataEmployment -> 'ANSATT' or 'ANSATT/status'. """
    # Only support for ANSATT type affs:
    if employment.kind not in (DataEmployment.HOVEDSTILLING,
                               DataEmployment.BISTILLING):
        raise NotImplementedError(
            "Cannot format employment of kind {0}".format(employment.kind))

    status = CATEGORY_TO_STATUS.get(employment.category)
    if not status:
        return "ANSATT"
    else:
        return "ANSATT/{0}".format(status)


def format_scoped_aff(employment, get_ous):
    """ DataEmployment -> '<weight>:<affiliation>@<sko>'. """
    return '{0}:{1}@{2}'.format(
        'primary' if employment.is_main() else 'secondary',
        format_employment_affiliation(employment),
        ','.join('{:02d}{:02d}{:02d}'.format(*sko_tuple)
                 for sko_tuple in get_ous(employment)))


def format_title(title):
    """ DataName -> <lang>:<title>. """
    return '{0}:{1}'.format(title.language.strip(),
                            title.value.strip())


def get_identifier(person):
    """ Get a person identifier from a SAPPerson object. """
    fnr = person.get_id(DataPerson.NO_SSN)
    if fnr:
        return 'norEduPersonNIN={:011d}'.format(int(fnr))
    # What now?
    raise ValueError("Person without national identifier number")


@contextmanager
def atomic_or_stdout(filename):
    """ A writable stream context.

    This context wraps the AtomicFileWriter context, so that we can handle the
    special case '-', where we want a stdout stream that doesn't close on
    context exit.
    """
    if filename == '-':
        yield sys.stdout
    else:
        with AtomicFileWriter(filename) as f:
            yield f


def main(inargs=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-i', '--input-file',
        default=DEFAULT_INPUT_FILE,
        help="sap2bas XML input file (default: %(default)s)",
        metavar='FILE',
    )
    parser.add_argument(
        '-o', '--output-file',
        default=DEFAULT_OUTPUT_FILE,
        help="LDIF output file, or '-' for stdout (default: %(default)s)",
        metavar='FILE',
    )
    parser.add_argument(
        '-u', '--utf8-data',
        dest='needs_base64',
        action='store_const',
        const=LDIFutils.needs_base64_readable,
        default=LDIFutils.needs_base64_safe,
        help="Allow utf-8 values in ldif",
    )
    Cerebrum.logutils.options.install_subparser(parser)
    parser.set_defaults(**{
        Cerebrum.logutils.options.OPTION_LOGGER_LEVEL: 'INFO',
    })
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start %s', parser.prog)
    logger.debug('args: %s', repr(args))

    LDIFutils.needs_base64 = args.needs_base64
    xml_parser = system2parser('system_sap')(args.input_file, logger)
    show_ou = OUSelector('ORG_OU', cereconf.OU_USAGE_SPREAD)
    get_ous = OrgTree(xml_parser.iter_ou(), show_ou)
    use_lang = LanguageSelector(cereconf.LDAP['pref_languages'])
    aff_selector = AffSelector(
        cereconf.LDAP_PERSON['affiliation_selector'])

    stats = {
        'seen': 0,
        'excluded': 0,
        'included': 0,
    }

    with atomic_or_stdout(args.output_file) as output:
        for person in xml_parser.iter_person():
            stats['seen'] += 1
            partial_affs = set()

            for emp in iterate_employments(person, aff_selector):
                try:
                    aff = format_scoped_aff(emp, get_ous)
                except Exception as e:
                    logger.warning('Ignoring employment person=%r emp=%r: %s',
                                   person, emp, e)
                    continue
                titles = [format_title(t)
                          for t in iterate_employment_titles(emp)
                          if use_lang(t.language)]
                partial_affs.add('{0}#{1}'.format(aff, ';'.join(titles)))

            if len(partial_affs) < 2:
                # We want at least two unique employments to output person
                stats['excluded'] += 1
                continue

            try:
                identifier = get_identifier(person)
            except ValueError:
                logger.warn("Missing NIN: {0}".format(str(person)))
                stats['excluded'] += 1
                continue

            stats['included'] += 1

            output.write(
                LDIFutils.entry_string(
                    identifier,
                    {'uioPersonPartialEmployment': list(sorted(partial_affs))},
                    add_rdn=False))

    logger.info("persons"
                " considered: {0[seen]:d},"
                " included: {0[included]:d},"
                " excluded: {0[excluded]:d}".format(stats))

    logger.info("Done %s", parser.prog)


if __name__ == "__main__":
    main()
