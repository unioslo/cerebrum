#!/usr/bin/env python
# coding: utf-8
#
# Copyright 2016-2019 University of Oslo, Norway
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
""" Generate reports on discrepancies in authoritative data. """
from __future__ import print_function, unicode_literals

import argparse
import logging
from collections import namedtuple
from functools import partial

import jinja2

import Cerebrum.logutils
import Cerebrum.logutils.options
import Cerebrum.utils.argutils
from Cerebrum.utils.atomicfile import AtomicFileWriter
from Cerebrum.Utils import Factory

logger = logging.getLogger(__name__)

TEMPLATE = u"""
<!DOCTYPE html>
<html>
  <head>
    <meta charset="{{ encoding | default('utf-8') }}" />
    <title>Names</title>
  </head>
  <body>
    <table>
      <tr>
        <th>entity</th>
        <th>name type</th>
        <th>sys</th>
        <th>name</th>
        <th>sys</th>
        <th>name</th>
      </tr>
      {% for item in data %}
      <tr>
        <td>{{ item['entity_id'] }}</td>
        <td>{{ item['name_variant'] }}</td>
        <td>{{ item['sys_a'] }}</td>
        <td>{{ item['name_a'] }}</td>
        <td>{{ item['sys_b'] }}</td>
        <td>{{ item['name_b'] }}</td>
      </tr>
      {% endfor %}
    </table>
  </body>
</html>
""".strip()


Name = namedtuple('Name', ('pid', 'system', 'variant', 'value'))


def get_names(db, system, variant, pid=None):
    """ Fetch names. """
    co = Factory.get(b'Constants')(db)
    pe = Factory.get(b'Person')(db)

    for row in pe.search_person_names(
            source_system=system,
            name_variant=variant,
            person_id=pid):
        yield Name(
            row['person_id'],
            co.AuthoritativeSystem(row['source_system']),
            co.PersonName(row['name_variant']),
            row['name'])


def compare_names(db, args):
    """ Generates an XML report for missing names. """
    co = Factory.get(b'Constants')(db)
    pe = Factory.get(b'Person')(db)
    variants = [co.PersonName(t[0]) for t in pe.list_person_name_codes()]

    logger.debug("Fetching names from {!s}".format(args.check_system))
    to_check = dict()
    for name in get_names(db, args.check_system, variants):
        to_check.setdefault(name.pid, dict())[name.variant] = name

    logger.debug("Fetching names for {:d} persons from {!s}".format(
        len(to_check), args.source_system))
    diff = dict()
    for name in get_names(
            db, args.source_system, variants, pid=to_check.keys()):
        if name.variant not in to_check[name.pid]:
            continue
        if to_check[name.pid][name.variant].value != name.value:
            diff.setdefault(name.pid, []).append(
                (name, to_check[name.pid][name.variant]))

    return diff


def format_rows(data):
    for pid, diffs in data.items():
        for source, diff in diffs:
            yield {
                'entity': source.pid,
                'name_variant': source.variant,
                'sys_a': source.system,
                'name_a': source.value,
                'sys_b': diff.system,
                'name_b': diff.value,
            }


def write_html_report(stream, codec, data):
    template_env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True)
    report = template_env.from_string(TEMPLATE)

    stream.write(
        report.render({
            'encoding': codec.name,
            'data': data,
        })
    )
    stream.write(u'\n')


DEFAULT_ENCODING = 'utf-8'


def get_const(db, const_type, const_val):
    u""" Gets a constant by value. """
    if isinstance(const_val, const_type):
        return const_val
    const = Factory.get('Constants')(db)
    value = const.human2constant(const_val, const_type)
    if value is None:
        raise ValueError(
            'Invalid {!s} {!r}'.format(const_type.__name__, const_val))
    return value


def argparse_const(db, const_type, const_val):
    u""" Get a constant from argument. """
    try:
        return get_const(db, const_type, const_val)
    except ValueError as e:
        raise argparse.ArgumentTypeError(e)


def main(inargs=None):
    db = Factory.get(b'Database')()
    co = Factory.get(b'Constants')(db)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-o', '--output',
        metavar='FILE',
        default='/tmp/report.html',
        help='output file for report, defaults to stdout')
    parser.add_argument(
        '-e', '--encoding',
        dest='codec',
        default=DEFAULT_ENCODING,
        type=Cerebrum.utils.argutils.codec_type,
        help="output file encoding, defaults to %(default)s")

    commands = parser.add_subparsers(help="available commands")

    # name
    name_command = commands.add_parser(
        'name',
        help="Generate report on differences in names.")
    name_command.set_defaults(func=compare_names)
    name_command.set_defaults(check_system=co.system_sap)
    name_command.add_argument(
        'source_system',
        type=partial(argparse_const, db, co.AuthoritativeSystem))

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    command = args.func
    del args.func

    # Other commands?
    logger.info('Generating report ({!s})'.format(args.output))
    with AtomicFileWriter(args.output,
                          mode='w',
                          encoding=args.codec.name) as af:

        report = command(db, args)
        write_html_report(af, args.codec, format_rows(report))

    logger.info("report written to %r", args.output)
    logger.info('Done')


if __name__ == '__main__':
    main()
