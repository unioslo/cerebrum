#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2006-2019 University of Oslo, Norway
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
Build an XML file with Cerebrum data for evalg 2.

This script generates an XML export with users for the evalg application.
Every person in Cerebrum is included, regardless of whether they have user
accounts or not.


Format
------
The XML document contains a single /data node, with zero or more /data/person
nodes.  Each person node will have some attributes with information about that
person.

::

    <?xml version="1.0" encoding="utf-8"?>
    <data>
      <person fnr="01017000000" first_name="Ola" last_name="Nordmann"
              uname="olan" email="olan@example.org"/>
    ...
    </data>


History
-------
This script was previously a part of the old cerebrum_config repository. It was
moved into the main Cerebrum repository, as it was currently in use by many
deployments of Cerebrum.

The original can be found in cerebrum_config.git, as
'bin/uio/fetch_valg_persons.py' at:

  commit: e83e053edc03dcd399775fadd9833101637757ef
  Merge: bef67be2 3bfbd8a2
  Date:  Wed Jun 19 16:07:06 2019 +0200
"""
from __future__ import unicode_literals

import argparse
import logging
import sys

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.Utils import XMLHelper
from Cerebrum.utils.argutils import codec_type
from Cerebrum.utils.atomicfile import AtomicFileWriter

logger = logging.getLogger(__name__)


def get_output_stream(filename, codec):
    """Get a unicode-compatible stream to write."""
    if filename == '-':
        stream = sys.stdout
    else:
        stream = AtomicFileWriter(filename, mode='w', encoding=codec.name)
    return stream


def read_exempt_file(filename):
    """Read person_id values from a file"""
    logger.debug('Fetching person_id values from %r', filename)
    with open(filename) as fp:
        for lineno, raw_line in enumerate(fp, 1):
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue
            try:
                yield int(line.strip())
            except ValueError:
                logger.error('Invalid person_id on line %d: %r',
                             lineno, raw_line)
                raise


def get_system_lookup_order(co):
    order = tuple(co.human2constant(value, co.AuthoritativeSystem)
                  for value in cereconf.SYSTEM_LOOKUP_ORDER)
    for n in order:
        int(n)
    return order


class Cache(object):
    """Cache evalg related person info."""

    def __init__(self, db, lookup_order):
        self.db = db
        self._sys_priority = dict((sys, idx)
                                  for idx, sys in enumerate(lookup_order))
        self._sys_default = len(self._sys_priority)
        # caches -> {<person-id>: {<type>: [(<source>, <value>), ...]}}
        self._name_cache = {}
        self._id_cache = {}

    def get_system_priority(self, sys):
        return self._sys_priority.get(sys, self._sys_default)

    def cache_names(self, name_variant):
        """Cache names from all source systems of a given type or types."""
        pe = Factory.get('Person')(self.db)
        for row in pe.search_person_names(name_variant=name_variant):
            person_names = self._name_cache.setdefault(row['person_id'], {})
            variant = person_names.setdefault(row['name_variant'], [])
            variant.append((row['source_system'], row['name']))

    def cache_ids(self, id_type):
        """Cache external ids from all source systems of a given type."""
        pe = Factory.get('Person')(self.db)
        for row in pe.search_external_ids(id_type=id_type,
                                          fetchall=False):
            person_ids = self._id_cache.setdefault(row['entity_id'], {})
            id_type = person_ids.setdefault(row['id_type'], [])
            id_type.append((row['source_system'], row['external_id']))

    def get_name(self, person_id, name_variant):
        """Get a previously cached name for a given person."""
        for _, name in sorted(
                self._name_cache.get(person_id, {}).get(name_variant, []),
                key=lambda v: self.get_system_priority(v[0])):
            return name
        return None

    def get_id(self, person_id, id_type):
        """Get a previously cached external id for a given person."""
        for _, extid in sorted(
                self._id_cache.get(person_id, {}).get(id_type, []),
                key=lambda v: self.get_system_priority(v[0])):
            return extid
        return None


xml_person_attrs = ('fnr', 'first_name', 'last_name', 'uname', 'email')


def get_persons(db, domain, use_feide, exempt_list):
    """
    Fetch person data from Cerebrum.

    :param domain:
        Domain to generate data for

    :param use_feide:
        Include domain in the uname field

    :param exempt_list:
        A set of person_id values to omit

    :rtype: generator
    :returns:
        Person dicts with keys from xml_person_attrs.
    """
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    person = Factory.get('Person')(db)
    stats = {'exempt': 0, 'no-name': 0, 'no-id': 0, 'include': 0}

    def fmt_domain_user(username):
        return '{}@{}'.format(username, domain)

    src_sys_order = get_system_lookup_order(co)
    person_cache = Cache(db, src_sys_order)

    # Fetch birth-no from most-significant source system
    logger.info("caching external_ids...")
    person_cache.cache_ids(co.externalid_fodselsnr)
    logger.debug('cached external id for %d persons',
                 len(person_cache._id_cache))

    logger.info('caching person names...')
    person_cache.cache_names((co.name_first, co.name_last))
    logger.info('cached names for %d persons', len(person_cache._name_cache))

    pid2uname = {}
    pid2email = {}
    logger.info("caching primary accounts...")
    for row in ac.list_accounts_by_type(primary_only=True):
        pid = int(row['person_id'])
        assert pid not in pid2uname
        ac.find(row['account_id'])
        pid2uname[pid] = ac.account_name
        try:
            pid2email[pid] = ac.get_primary_mailaddress()
        except Exception:
            pass
        ac.clear()
    logger.debug('found %d primary accounts, %d primary email addresses',
                 len(pid2uname), len(pid2email))

    logger.info("fetching persons...")
    for row in person.list_persons():
        pid = row['person_id']
        if pid in exempt_list:
            logger.info('skipping person_id=%r: in exept list', pid)
            stats['exempt'] += 1
            continue

        person_data = dict((key, None) for key in xml_person_attrs)

        fname = person_cache.get_name(pid, co.name_first)
        lname = person_cache.get_name(pid, co.name_last)
        if fname or lname:
            person_data['first_name'] = fname
            person_data['last_name'] = lname
        else:
            logger.info('skipping person_id=%r, no usable name', pid)
            stats['no-name'] += 1
            continue

        fnr = person_cache.get_id(pid, co.externalid_fodselsnr)
        if fnr:
            person_data['fnr'] = fnr
        elif pid in pid2uname:
            # Use feide-id as fallback if fnr is lacking
            person_data['fnr'] = fmt_domain_user(pid2uname[pid])
        else:
            logger.info('skipping person_id=%r, no usable identifier', pid)
            stats['no-id'] += 1
            continue
        if pid in pid2uname:
            if use_feide:
                person_data['uname'] = fmt_domain_user(pid2uname[pid])
            else:
                person_data['uname'] = pid2uname[pid]
            if pid in pid2email:
                person_data['email'] = pid2email[pid]
        else:
            logger.debug('no account for person_id=%r', pid)

        stats['include'] += 1
        yield person_data
    logger.info('found %d persons (%s)', sum(stats.values()), repr(stats))


def write_xml(stream, persons):
    """
    :param persons:
        An iterable of person dicts.

        Each person dict should contain keys from person_cols
    """
    encoding = stream.encoding
    xml = XMLHelper(encoding=encoding)

    stream.write(xml.xml_hdr)
    stream.write("<data>\n")
    for person in persons:
        stream.write(xml.xmlify_dbrow(person, xml_person_attrs, 'person') +
                     "\n")
    stream.write("</data>\n")


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Generate evalg XML file",
    )
    parser.add_argument(
        '-f', '--use-feide',
        dest='use_feide',
        required=False,
        action='store_true',
        help='Format usernames as <username>@<org>',
    )
    parser.add_argument(
        '--exempt-file',
        dest='exempt_file',
        help='Omit person_id values found in %(metavar)s',
        metavar='<filename>',
    )
    parser.add_argument(
        '-x', '--exempt',
        dest='exempt_list',
        type=int,
        action='append',
        help='Omit person_id %(metavar)s',
        metavar='<person-id>',
    )
    parser.add_argument(
        '-e', '--encoding',
        dest='codec',
        type=codec_type,
        default='utf-8',
        help='XML encoding (default: %(default)s)',
        metavar='ENCODING',
    )
    parser.add_argument(
        'domain',
        help='Feide organization (e.g. uio.no)',
        metavar='<org>',
    )
    parser.add_argument(
        'filename',
        help='Write XML to %(metavar)s',
        metavar='<filename>',
    )
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)

    Cerebrum.logutils.autoconf('cronjob', args)
    logger.info('Start %s', parser.prog)
    logger.debug('args: %r', args)

    db = Factory.get('Database')()

    exempt_list = set()
    if args.exempt_file:
        exempt_list.update(read_exempt_file(args.exempt_file))
    if args.exempt_list:
        exempt_list.update(args.exempt_list)
    logger.info('Omitting %d persons from file=%r, args=%r',
                len(exempt_list), args.exempt_file, args.exempt_list)

    stream = get_output_stream(args.filename, args.codec)

    logger.debug('fetching person generator for %r', args.domain)
    persons = get_persons(db, args.domain, args.use_feide, exempt_list)

    logger.debug('starting output to %s', repr(stream))
    write_xml(stream, persons)

    stream.flush()
    if stream not in (sys.stdout, sys.stderr):
        stream.close()

    logger.info('XML written to %s', stream.name)
    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
