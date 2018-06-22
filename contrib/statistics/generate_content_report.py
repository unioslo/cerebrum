#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2006-2018 University of Oslo, Norway
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
""" Generate statistics report on the Cerebrum database state.

This program can generate two different sets of statistics; one that
presents various numeric data about the entities in the database
(number of accounts, number of persons by affiliation, etc) and one
that counts number of entities within various areas that may or may
not represent problems that need to be dealt with in some way. The
last variety can also provide the entity IDs that fall within the
given problematic topic (for lack of better term)
"""
import argparse
import logging
import sys

from six import text_type

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import codec_type

logger = logging.getLogger(__name__)


class DatabaseFormatter(object):
    """ Format database values and write to stream. """

    def __init__(self, stream, codec, db_encoding, details=False):
        self.stream = codec.streamwriter(stream)
        self.db_encoding = db_encoding
        self.details = bool(details)

    def u(self, db_value):
        if isinstance(db_value, bytes):
            return db_value.decode(self.db_encoding)
        return text_type(db_value)

    def write(self, *args, **kwargs):
        return self.stream.write(*args, **kwargs)

    def write_header(self, header, line='-'):
        line = line * ((len(header) // len(line)) + len(header) % len(line))
        self.write("\n%s\n%s\n" % (header, line))

    def write_entity(self, topic, result):
        """ Write entity results.

        :param result:
            the result of an SQL query, where the first (only?) column contains
            the entity_id of entities that fit the criterea of the particular
            test/search.
        """
        self.write("%s: %i\n" % (topic, len(result)))
        if self.details:
            ids = [text_type(row[0]) for row in result]
            self.write("Entity IDs for these are: ")
            self.write(", ".join(ids) + "\n")

    def write_multi(self, topic, result,
                    header=None, line_format=None, line_sep=" " * 3):
        """ write row data results.

        :param result:
            the result of an SQL query

        :param header:
            tuple with header values, must have the same length as each tuple
            in result
        """
        header = tuple(header or ())
        self.write("\n%s: %i\n" % (topic, len(result)))
        if self.details:
            if header:
                tmp = line_sep.join(header)
                self.write(tmp + "\n")
                self.write("-"*70 + "\n")
            for row in result:
                if line_format:
                    line = line_format % tuple(map(self.u, row))
                else:
                    line = line_sep.join(map(self.u, row))
                self.write(line + "\n")

    def write_grouped(self, topic, result):
        """ write grouped results.

        :param results:
            the result of an SQL query, where the first column contains the
            'label' while the second column represents the count/result
            associated with that particular label.

        Any sorting should be done before the result is sent to the
        method.
        """
        self.write("%s:\n" % topic)
        for row in result:
            self.write("    %-36s: %6i\n" % (self.u(row[0]), int(row[1])))

    def write_grouped_nested(self, topic, result):
        """ write gropued, nested results.

        :param result:
            the result of an SQL query, where the first column contains the
            main categories, the second column represents the sub-categories
            and the third column represents the count/result associated with
            that particular category/sub-category.

        Any sorting should be done before the result is sent to the
        method.
        """
        self.write("%s:\n" % topic)
        outer_group = ""
        for row in result:
            if row[0] != outer_group:
                outer_group = row[0]
                group = row[0]
            else:
                group = ""
            self.write("    %-15s %-20s: %6i\n" %
                       (self.u(group), self.u(row[1]), int(row[2])))

    def write_single(self, topic, result):
        """ write a single result.

        :param result:
            the result of an SQL query, where the first (only?) column of the
            first (only?) row contains the number the represents the result for
            this particular test/search.

        """
        self.write("\n%-40s: %6i\n" % (topic, int(result[0][0])))


def generate_person_statistics(db, presenter):
    co = Factory.get("Constants")(db)

    presenter.write_header("Reports dealing with person entities")

    # Report people that lack both a first name and a last name
    result = db.query(
        """
        SELECT person_id
        FROM [:table schema=cerebrum name=person_info]
        EXCEPT
        SELECT pn1.person_id
        FROM [:table schema=cerebrum name=person_name] pn1,
             [:table schema=cerebrum name=person_name] pn2
        WHERE
            pn1.source_system not in (:system_fs, :system_sap) AND
            pn1.person_id = pn2.person_id AND
            pn1.name_variant = :firstname AND
            pn2.name_variant = :lastname
        """,
        {"firstname": int(co.name_first),
         "lastname": int(co.name_last),
         "system_fs": int(co.system_fs),
         "system_sap": int(co.system_sap), })
    presenter.write_entity("Number of people lacking both first and last name",
                           result)

    # TODO 2007-01-17 amveha: people without f;dselsnummer (11 digits)
    # or with f;dselsnummer not associated with an authoritative
    # source system.

    # People without birthdates or birthdates in the future
    # TBD 2007-01-03 amveha: Are there other criterea that can qualify
    # as invalid wrt birthdates? Such as being born on Jan 1 1901?
    result = db.query(
        """
        SELECT person_id
        FROM [:table schema=cerebrum name=person_info]
        WHERE
            -- No birthdate set:
            birth_date is NULL OR
            -- Birthdate in future:
            birth_date > NOW()
        """)
    presenter.write_entity("Number of people with unsatisfactory birthdates",
                           result)

    # Report people without any accounts
    result = db.query(
        """
        SELECT person_id
        FROM [:table schema=cerebrum name=person_info]
        EXCEPT
        SELECT owner_id
        FROM [:table schema=cerebrum name=account_info]
        """)
    presenter.write_entity("Number of people with no accounts", result)

    # People without any affiliations
    result = db.query(
        """
        SELECT person_id
        FROM [:table schema=cerebrum name=person_info]
        EXCEPT
        SELECT person_id
        FROM [:table schema=cerebrum name=person_affiliation_source]
        WHERE deleted_date is NULL OR deleted_date > NOW()
        """)
    presenter.write_entity("Number of people with no affiliations", result)


def generate_person_name_statistics(db, presenter, details=False):
    # Report people with to many white space characters in the name
    co = Factory.get("Constants")(db)

    result = db.query(
        """
        SELECT distinct pn.person_id, eei.external_id, pn.name
        FROM [:table schema=cerebrum name=person_name] pn,
             [:table schema=cerebrum name=entity_external_id] eei,
             [:table schema=cerebrum name=authoritative_system_code] ac,
             [:table schema=cerebrum name=person_affiliation] pa
        WHERE pn.name similar to '%%  +%%' AND
              pn.name_variant = :firstname AND
              eei.entity_id = pn.person_id AND
              eei.id_type = :sap_ansattnr AND
              ac.code = :system_sap AND
              ac.code = pn.source_system AND
              pa.person_id = pn.person_id AND
              pa.affiliation = :affiliation_ansatt
              order by pn.person_id
        """,
        {
            "firstname": int(co.name_first),
            "sap_ansattnr": int(co.externalid_sap_ansattnr),
            "system_sap": int(co.system_sap),
            "affiliation_ansatt": int(co.affiliation_ansatt),
        }
    )
    topic = ("Number of persons from SAP with too many white spaces"
             " in first name")
    header = ("Person id", "SAP ansattnr", "Name")
    line_format = "%%%ds   %%%ds   %%s" % (len(header[0]), len(header[1]))
    presenter.write_multi(topic, result, header, line_format)


def generate_account_statistics(db, presenter):
    co = Factory.get("Constants")(db)

    presenter.write_header("Reports dealing with account entities")

    # Accounts without password information
    result = db.query(
        """
        SELECT account_id
        FROM [:table schema=cerebrum name=account_info]
        EXCEPT
        SELECT account_id
        FROM [:table schema=cerebrum name=account_authentication]
        """)
    presenter.write_entity("Number of accounts without password info", result)

    # Accounts without spread
    result = db.query(
        """
        SELECT account_id
        FROM [:table schema=cerebrum name=account_info]
        EXCEPT
        SELECT entity_id
        FROM [:table schema=cerebrum name=entity_spread]
        WHERE entity_type = :entity_type_account
        """,
        {"entity_type_account": int(co.entity_account)})

    presenter.write_entity("Number of accounts without spread", result)

    # TODO 2007-01-17 amveha: accounts without home area.

    # Personal user accounts without account_type
    result = db.query(
        """
        SELECT account_id
        FROM [:table schema=cerebrum name=account_info]
        EXCEPT
        SELECT account_id
        FROM [:table schema=cerebrum name=account_type]
        """)
    presenter.write_entity("Number of personal accounts without account_type",
                           result)

    # System (non-personal) accounts without np_type set
    # TBD 2007-01-05 amveha: This test is redundant, since there is a
    # check-contraint in the DB that makes the combination
    # invalid. Remove test?
    result = db.query(
        """
        SELECT account_id
        FROM [:table schema=cerebrum name=account_info]
        WHERE
            owner_type = :entity_type_group AND
            np_type IS NULL
        """,
        {"entity_type_group": int(co.entity_group)})
    presenter.write_entity("Number of system accounts without np_type", result)


def generate_group_statistics(db, presenter, details=False):
    co = Factory.get("Constants")(db)

    presenter.write_header("Reports dealing with group entities")

    # Groups without any members at all, directly or indirectly
    result = db.query(
        """
        SELECT group_id
        FROM [:table schema=cerebrum name=group_info]
        EXCEPT
        SELECT group_id
        FROM [:table schema=cerebrum name=group_member]
        """)
    presenter.write_entity("Number of groups without any members at all",
                           result)

    # TODO 2007-01-17 amveha: Groups without any members at all,
    # directly or indirectly.

    # Groups without spread
    result = db.query(
        """
        SELECT group_id
        FROM [:table schema=cerebrum name=group_info]
        EXCEPT
        SELECT entity_id
        FROM [:table schema=cerebrum name=entity_spread]
        WHERE entity_type = :entity_type_group
        """,
        {"entity_type_group": int(co.entity_group)})

    presenter.write_entity("Number of groups without spread", result)

    # Groups without descriptions
    result = db.query(
        """
        SELECT group_id
        FROM [:table schema=cerebrum name=group_info]
        WHERE
            -- No description set...
            description is NULL OR
            -- ... or description is empty
            description LIKE ''
        """)
    presenter.write_entity("Number of groups without description", result)


def generate_ou_statistics(db, presenter, details=False):
    co = Factory.get("Constants")(db)

    presenter.write_header("Reports dealing with OU entities")

    # TODO 2007-01-17: Valid OU-formats (stedkode or OU)

    # OUs with name discrepencies
    for name_type in (
            co.ou_name,
            co.ou_name_acronym,
            co.ou_name_short,
            co.ou_name_long,
            co.ou_name_display,
    ):
        result = db.query(
            """
            SELECT ou.ou_id
            FROM [:table schema=cerebrum name=ou_info] ou,
                 [:table schema=cerebrum name=entity_language_name] name
            WHERE
                ou.ou_id = name.entity_id AND
                name.name_variant = :name_type AND
                name.name LIKE '' OR
                name.name is NULL
            """,
            {'name_type': name_type})
        presenter.write_entity(
            "Number of OUs with no '%s'" % text_type(name_type),
            result)

    # Orphan OUs (no parent)
    result = db.query(
        """
        SELECT ou_id
        FROM [:table schema=cerebrum name=ou_structure]
        WHERE parent_id IS NULL
        """)
    presenter.write_entity("Number of OUs with no parent", result)

    # TBD 2007-01-17 amveha: The spec calls for structure dump, but
    # also that it might not be necessary. Do we want it or not?


def generate_cerebrum_numbers(db, presenter):
    co = Factory.get("Constants")(db)

    # TODO 2007-01-17 amveha: Modules in use

    # Person count...
    result = db.query(
        """
        SELECT COUNT(*)
        FROM [:table schema=cerebrum name=person_info]
        """)
    presenter.write_single("Number of persons", result)

    # ... per affiliation...
    result = db.query(
        """
        SELECT pac.code_str, count(distinct pa.person_id)
        FROM [:table schema=cerebrum name=person_affiliation] pa,
             [:table schema=cerebrum name=person_affiliation_code] pac
        WHERE pa.affiliation = pac.code
        GROUP BY pac.code_str
        ORDER BY pac.code_str
        """)
    presenter.write_grouped("- distributed by affiliation", result)

    # ... and by affiliation status
    result = db.query(
        """
        SELECT pac.code_str, pasc.status_str, count(distinct pas.person_id)
        FROM [:table schema=cerebrum name=person_affiliation_source] pas,
             [:table schema=cerebrum name=person_affiliation_code] pac,
             [:table schema=cerebrum name=person_aff_status_code] pasc
        WHERE
            pas.affiliation = pac.code AND
            pas.status = pasc.status
        GROUP BY pac.code_str, pasc.status_str
        ORDER BY pac.code_str, pasc.status_str
        """)
    presenter.write_grouped_nested("- distributed by affiliation status",
                                   result)

    # Account-count...
    result = db.query(
        """
        SELECT COUNT(*)
        FROM [:table schema=cerebrum name=account_info]
        """)
    presenter.write_single("Number of accounts", result)

    # ... per account_type ...
    result = db.query(
        """
        SELECT pac.code_str, count(*)
        FROM [:table schema=cerebrum name=account_type] at,
             [:table schema=cerebrum name=person_affiliation_code] pac
        WHERE at.affiliation = pac.code
        GROUP BY pac.code_str
        ORDER BY pac.code_str
        """)
    presenter.write_grouped("- distributed by account type", result)

    # ... per spread...
    result = db.query(
        """
        SELECT sc.code_str, count(*)
        FROM [:table schema=cerebrum name=entity_spread] es,
             [:table schema=cerebrum name=spread_code] sc
        WHERE
             es.spread = sc.code AND
             es.entity_type = :entity_type_account
        GROUP BY sc.code_str
        ORDER BY sc.code_str
        """,
        {"entity_type_account": int(co.entity_account)})
    presenter.write_grouped("- distributed by spread", result)
    # TODO 2007-01-17 amveha: - per host/disk

    # OU-count
    result = db.query(
        """
        SELECT COUNT(*)
        FROM [:table schema=cerebrum name=ou_info]
        """)
    presenter.write_single("Number of OUs", result)

    # Group-count...
    result = db.query(
        """
        SELECT COUNT(*)
        FROM [:table schema=cerebrum name=group_info]
        """)
    presenter.write_single("Number of groups", result)

    # ...per spread...
    result = db.query(
        """
        SELECT sc.code_str, count(*)
        FROM [:table schema=cerebrum name=entity_spread] es,
             [:table schema=cerebrum name=spread_code] sc
        WHERE
            es.spread = sc.code AND
            es.entity_type = :entity_type_group
        GROUP BY sc.code_str
        ORDER BY sc.code_str
        """,
        {"entity_type_group": int(co.entity_group)})
    presenter.write_grouped("- distributed by spread", result)

    # TODO 2007-01-17 amveha: Migrated persons not affected by
    # authoratative source systems.

    # TODO 2007-01-17 amveha: Registered e-mail-domains.

    # TODO 2007-01-17 amveha: Resgistered hosts/disks (with description).


DEFAULT_ENCODING = 'utf-8'


def main(inargs=None):
    """Main processing hub for program."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-f', '--file',
        dest='output',
        metavar='FILE',
        type=argparse.FileType('w'),
        default='-',
        help='output file for report, defaults to stdout')
    parser.add_argument(
        '--encoding',
        dest='codec',
        default=DEFAULT_ENCODING,
        type=codec_type,
        help="output file encoding, defaults to %(default)s")

    parser.add_argument(
        '-a', '--all',
        action='store_true',
        default=False,
        help='Generate all reports')

    parser.add_argument(
        '-n', '--numbers',
        action='store_true',
        default=False,
        help='Generate generic statistics about database content')

    parser.add_argument(
        '-e', '--entities',
        action='store_true',
        default=False,
        help='Generate reports on entities that may or may not'
             'represent things that need to be addressed')

    parser.add_argument(
        '-s', '--sap_names',
        dest='names',
        action='store_true',
        default=False,
        help='')

    parser.add_argument(
        '-d', '--details',
        action='store_true',
        default=False,
        help="For '--entitities', provide entity IDs for the"
             "entities 'suffering' the given 'problem'")

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('console', args)

    logger.info('Start of script %s', parser.prog)
    logger.debug("args: %r", args)

    db = Factory.get("Database")()

    presenter = DatabaseFormatter(args.output, args.codec, db.encoding,
                                  details=args.details)

    if args.all or args.numbers:
        presenter.write_header("Cerebrum in numbers", line="=")
        generate_cerebrum_numbers(db, presenter)

    if args.all or args.entities:
        presenter.write_header("Information about possibly problematic"
                               " entities", line="=")
        generate_person_statistics(db, presenter)
        generate_account_statistics(db, presenter)
        generate_group_statistics(db, presenter)
        generate_ou_statistics(db, presenter)

    if args.all or args.names:
        presenter.write_header("Information about problematic person names",
                               line="=")
        generate_person_name_statistics(db, presenter)

    args.output.flush()
    if args.output is not sys.stdout:
        args.output.close()

    logger.info('Report written to %s', args.output.name)
    logger.info('Done with script %s', parser.prog)


if __name__ == "__main__":
    main()
