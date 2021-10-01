#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2021 University of Oslo, Norway
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
""" Generate an HTML report with persons who possibly are missing from DFØ.

This script can be deleted when the UiOSAP affs have been removed.
Generates a list of persons, who have a aff from UiOSAP but not one from DFØ.
"""
import argparse
import logging
import sys

from jinja2 import Environment
from six import text_type

from datetime import datetime

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.Errors import NotFoundError
from Cerebrum.utils.argutils import codec_type

logger = logging.getLogger(__name__)


# TODO: Move to actual template, or at least use a base template
template = u"""
<!DOCTYPE html>
<html>
  <head>
    <meta http-equiv="Content-Type"
          content="text/html; charset={{ encoding | default('utf-8') }}">
    <title>Personer fra UiOSAP uten tilknytning i DFØ</title>
    <style type="text/css">
      /* <![CDATA[ */
      h1 {
        margin: 1em .8em 1em .8em;
        font-size: 1.4em;
      }
      h2 {
        margin: 1.5em 1em 1em 1em;
        font-size: 1em;
      }
      table + h1 {
        margin-top: 3em;
      }
      table {
        border-collapse: collapse;
        width: 100%;
        text-align: left;
      }
      table thead {
        border-bottom: solid gray 1px;
      }
      table th, table td {
        padding: .5em 1em;
        width: 10%;
      }
      .meta {
        color: gray;
        text-align: right;
      }
      /* ]] >*/
    </style>
  </head>
  <body>
    <p class="meta">
      UiOSAP personer uten tilknytning fra DFØ
    </p>

    {% for fak in data | sort %}
    <h1>{{ fak }}</h1>

    {% for sko in data[fak] | sort %}
    <h2>{{ sko }}</h2>
    <table>
      <thead>
        <tr>
          <th>Navn</th>
          <th>Tilknytning</th>
          <th>entity_id</th>
          <th>Ansattnr (DFØ)</th>
          <th>Brukere</th>
        </tr>
      </thead>
      {% for person in data[fak][sko] | sort(attribute='pid') %}
      <tr>
        <td>{{ person['name'] }}</td>
        <td>{{ person['status'] }}</td>
        <td>{{ person['pid'] }}</td>
        <td>{{ person['dfoid'] }}</td>
        <td>{{ person['accounts'] }}</td>
      </tr>
      {% endfor %}
    </table>
    {% endfor %}
    {% endfor %}

    <p class="meta">
      Generated: {{ when }}
    </p>
  </body>
</html>
""".strip()


def get_sap_persons_missing_dfo_aff(db):
    co = Factory.get('Constants')(db)
    pe = Factory.get('Person')(db)
    ac = Factory.get('Account')(db)
    ou = Factory.get('OU')(db)

    def _u(db_value):
        if db_value is None:
            return text_type('')
        if isinstance(db_value, bytes):
            return db_value.decode(db.encoding)
        return text_type(db_value)

    ou2sko = dict((row['ou_id'], ("%02d%02d%02d" % (row['fakultet'],
                                                    row['institutt'],
                                                    row['avdeling'])))
                  for row in ou.get_stedkoder())
    sko2name = dict((ou2sko[row['entity_id']], row['name'])
                    for row in ou.search_name_with_language(
                        name_variant=co.ou_name_display,
                        name_language=co.language_nb))

    dfosap = set(r['person_id'] for r in
                 pe.list_affiliations(source_system=co.system_dfo_sap))
    logger.debug('Nr of people from DFO_SAP: {}'.format(len(dfosap)))

    guests = set(r['person_id'] for r in
                 pe.list_affiliations(source_system=co.system_manual)
                 if r['status'] != int(co.affiliation_tilknyttet_fagperson))
    logger.debug('Nr of people registered in tmp guest sys: {}'
                 .format(len(guests)))

    logger.info('Finding UiOSAP affiliations...')
    nr_sapuio = 0
    processed = set()
    for affiliation in pe.list_affiliations(source_system=co.system_sap):
        p_id = affiliation['person_id']

        if p_id in processed:
            continue
        processed.add(p_id)
        if p_id in dfosap:
            continue
        if p_id in guests:
            continue

        pe.clear()
        try:
            pe.find(p_id)
        except NotFoundError:
            # Typically happens when a person-object has been joined
            # with another one since its creation
            continue

        nr_sapuio += 1

        name = pe.search_person_names(
            person_id=p_id,
            name_variant=co.name_full)[0]['name']

        try:
            dfoid = pe.get_external_id(
                source_system=co.system_dfo_sap,
                id_type=co.externalid_dfo_pid)[0]['external_id']
        except IndexError:
            dfoid = ''

        accounts = []
        for row in ac.search(owner_id=p_id):
            ac.clear()
            ac.find(row['account_id'])
            if ac.is_reserved() or ac.is_deleted() or ac.is_expired():
                status = '(inaktiv)'
            elif ac.get_entity_quarantine():
                status = '(karantene)'
            else:
                status = ''
            accounts.append('%s %s' % (row['name'], status))

        for row in pe.list_affiliations(
                person_id=p_id,
                source_system=co.system_sap):

            sko = ou2sko[row['ou_id']]
            fak = sko[:2] + "0000"

            yield {
                'pid': int(p_id),
                'ou': u' - '.join((text_type(sko), _u(sko2name.get(sko, '')))),
                'faculty': _u(sko2name.get(fak)) or text_type(fak),
                'name': _u(name),
                'status': text_type(co.PersonAffStatus(row['status'])),
                'dfoid': text_type(dfoid),
                'accounts': u', '.join((_u(a) for a in accounts)),
            }
    logger.debug("People reported: {}".format(nr_sapuio))


def aggregate(iterable, *keys):
    """ Take an iterable of dicts to output, and organize in groups.

    >>> aggregate([{'a': 'foo', 'b': 'x'}, {'a': 'foo', 'b': 'y'}], 'b')
    {'x': [{'a': 'foo', 'b': 'x'}], 'y': [{'a': 'foo', 'b': 'y'}]}

    """
    if len(keys) < 1:
        raise TypeError("aggregate takes at least two arguments (1 given)")

    root = dict()
    group_defaults = tuple(zip(keys, [dict] * (len(keys) - 1) + [list]))

    for item in iterable:
        group = root
        for key, default in group_defaults:
            group = group.setdefault(item[key], default())
        group.append(item)
    return root


def write_html_report(stream, codec, persons_missing_dfo_aff):
    output = codec.streamwriter(stream)
    template_env = Environment(trim_blocks=True, lstrip_blocks=True)
    report = template_env.from_string(template)

    output.write(
        report.render({
            'encoding': codec.name,
            'data': persons_missing_dfo_aff,
            'when': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        })
    )
    output.write('\n')


DEFAULT_ENCODING = 'utf-8'


def main(inargs=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-o', '--output',
        metavar='FILE',
        type=argparse.FileType('w'),
        default='-',
        help='output file for report, defaults to stdout')
    parser.add_argument(
        '-e', '--encoding',
        dest='codec',
        default=DEFAULT_ENCODING,
        type=codec_type,
        help="output file encoding, defaults to %(default)s")

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    db = Factory.get('Database')()

    persons_missing_dfo_aff = aggregate(
        get_sap_persons_missing_dfo_aff(db),
        'faculty',
        'ou')

    write_html_report(args.output, args.codec, persons_missing_dfo_aff)

    args.output.flush()
    if args.output is not sys.stdout:
        logger.info("We are in closing section")
        args.output.close()

    logger.info('Report written to %s', args.output.name)
    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
