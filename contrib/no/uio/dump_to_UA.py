#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2004-2018 University of Oslo, Norway
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
Generates a dump file for the UA database.

The rules for the dump are thus:

* Every person with an employment (tilsetting) record or with a student
  affiliation is a candidate for ending up in the dump file.
* Every such person can potentially have multiple entries in the dump file.
* An entry consists of 29 fields separated by semicolon

* Students[1] would have one entry per student affiliation
* Employees[2] would have one entry per active employment[3] (tilsetting)

However, since the UA system does not cope with multiple student records,
none of them end up in the dump file. I.e. only the employee-related records
are output.

[1] def: persons having affiliation STUDENT

[2] def: persons having an employment record (tilsetting)

[3] def: employment records (tilsetting) that have a start date (dato_fra)
         in the past and end date (dato_til) either in the future or
         unknown. Furthermore, such employments (tilsetting) shall not have
         active leaves of absence (permisjon) totalling 100%.
"""
from __future__ import unicode_literals

import argparse
import ftplib
import io
import logging
import os
import time

from six import text_type

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Utils import Factory, read_password
from Cerebrum.utils.atomicfile import AtomicFileWriter
from Cerebrum.utils.transliterate import for_encoding
from Cerebrum.modules.xmlutils.system2parser import system2parser


logger = logging.getLogger(__name__)

encoding = 'latin1'
transliterate = for_encoding(encoding)


def fnr2names(person, const, fnr):
    """Locate person's first and last names from a given fnr."""
    # Force SAP to be the first source system to be tried
    systems = [const.system_sap]
    systems.extend([getattr(const, name)
                    for name in cereconf.SYSTEM_LOOKUP_ORDER])
    for system in systems:
        try:
            person.clear()
            person.find_by_external_id(const.externalid_fodselsnr,
                                       fnr, system)
            return locate_names(person, const)
        except Errors.NotFoundError:
            pass

    return None, None


def locate_names(person, const):
    """ Get a persons (first, last) name """
    first, last = "", ""
    systems = [const.system_sap]
    systems.extend([getattr(const, name)
                    for name in cereconf.SYSTEM_LOOKUP_ORDER])

    for system in systems:
        try:
            first = person.get_name(system, const.name_first)
            break
        except Errors.NotFoundError:
            pass

    for system in systems:
        try:
            last = person.get_name(system, const.name_last)
            break
        except Errors.NotFoundError:
            pass

    if not first:
        logger.debug("No first name for %s", person.entity_id)

    if not last:
        logger.debug("No last name for %s", person.entity_id)

    return first, last


def prepare_entry(fnr, systemnr, korttype, fornavn, etternavn, arbeidssted,
                  startdato="", sluttdato=""):
    """
    Return a suitably formatted entry.
    """
    #
    # Field layout (in order):
    #
    # 1.     fnr
    # 2.     systemnr number
    # 3.     korttype
    # 4.     fornavn
    # 5.     etternavn
    # 6-11.  adgangsnivå            -- blank
    # 12.    sist betalt sem.avgift -- blank
    # 13.    betalingsdato 	    -- blank
    # 14.    startdato
    # 15.    sluttdato
    # 16-18. misc                   -- blank
    # 19.    arbeidssted
    # 20-29.                        -- blank
    result = [str(fnr) + systemnr, systemnr, korttype, fornavn, etternavn,
              "", "", "", "", "", "",
              "",
              "",
              startdato, sluttdato,
              "", "", "",
              arbeidssted]
    result.extend([""] * 10)
    # FIXME: The fields should be quoted
    return ";".join(result) + "\n"


def leave_covered(xml_person, employment):
    """
    Check whether a given employment (tilsetting) entry has active leaves of
    absence (permisjon) totalling to 100% (or more :))
    """
    total = 0
    for l in employment.leave:
        total += int(l['percentage'])
    return total >= 100


def process_employee(db_person, ou, const, xml_person, fnr, stream):
    """
    Output an UA entry corresponding to PERSON's employment represented by
    DB_ROW.
    """
    # TBD, Should we check that names from db and xml are consistent?
    first_name, last_name = locate_names(db_person, const)

    # Check all employments (tilsettinger) for this person
    for employment in xml_person.iteremployment():
        # TBD, this might be unnecessary
        if leave_covered(xml_person, employment):
            logger.debug("%s has tilsetting %s which has >= 100%% coverage",
                         fnr, employment)
            return

        if not employment.place:
            logger.warning("No SKO for %s: %s", fnr, employment)
        stedkode = "%02d%02d%02d" % employment.place[1]

        startdato = ""
        if employment.start:
            startdato = employment.start.strftime("%d.%m.%Y")
        sluttdato = ""
        if employment.end:
            sluttdato = employment.end.strftime("%d.%m.%Y")

        first_name = transliterate(first_name)
        last_name = transliterate(last_name)

        # systemnr = 1 for students
        # systemnr = 2 for employees
        stream.write(prepare_entry(fnr=fnr,
                                   systemnr="2",
                                   korttype="Tilsatt UiO",
                                   fornavn=first_name,
                                   etternavn=last_name,
                                   arbeidssted=stedkode,
                                   startdato=startdato,
                                   sluttdato=sluttdato))


def generate_output(db, stream, do_employees, sysname, person_file):
    """
    Create dump for UA
    """
    db_person = Factory.get("Person")(db)
    ou = Factory.get("OU")(db)
    const = Factory.get("Constants")(db)

    if do_employees:
        logger.info("Extracting employee info from %s", person_file)

        source_system = getattr(const, sysname)
        parser = system2parser(sysname)(person_file, logger, False)

        # Go through all persons in person_info_file
        for xml_person in parser.iter_person():
            try:
                fnr = xml_person.get_id(xml_person.NO_SSN)
                if fnr is None:
                    sapnr = xml_person.get_id(xml_person.SAP_NR)
                    logger.warn('Employee %s has no fnr', sapnr)
                    continue
                db_person.find_by_external_id(const.externalid_fodselsnr, fnr,
                                              source_system=source_system)
            except Errors.NotFoundError:
                logger.warn("Couldn't find person with fnr %s in db", fnr)
                continue

            process_employee(db_person, ou, const, xml_person, fnr, stream)
            db_person.clear()


def do_sillydiff(db, dirname, oldfile, newfile, outfile):
    """ This very silly. Why? """
    today = time.strftime("%d.%m.%Y")
    try:
        oldfile = io.open(os.path.join(dirname, oldfile), "r",
                          encoding=encoding)
        line = oldfile.readline()
        line = line.rstrip()
    except IOError:
        logger.warn("Warning, old file did not exist, assuming first run ever")
        os.link(os.path.join(dirname, newfile),
                os.path.join(dirname, outfile))
        return

    old_dict = dict()
    while line:
        key = line[0:12]
        value = old_dict.get(key, list())
        value.append(line[13:])
        old_dict[key] = value
        line = oldfile.readline()
        line = line.rstrip()
    oldfile.close()

    out = AtomicFileWriter(os.path.join(dirname, outfile), 'w',
                           encoding=encoding)
    newin = io.open(os.path.join(dirname, newfile), encoding=encoding)

    for newline in newin:
        newline = newline.rstrip()
        pnr = newline[0:12]
        data = newline[13:]
        if pnr in old_dict:
            if data not in old_dict[pnr]:
                # Some change, want to update with new values.
                out.write(newline + "\n")
            else:
                old_dict[pnr].remove(data)
            # If nothing else is left, delete the key from the dictionary
            if not old_dict[pnr]:
                del old_dict[pnr]
        else:
            # completely new entry, output unconditionally
            out.write(newline + "\n")

    # Now, there is one problem left: we cannot output the old data blindly,
    # as people's names might have changed. So, we force *every* old record to
    # the current names in Cerebrum. This may result in the exactly same
    # record being output twice, but it should be fine.
    person = Factory.get("Person")(db)
    const = Factory.get("Constants")(db)
    logger.debug("%d old records left", len(old_dict))
    for leftpnr in old_dict:
        # FIXME: it is unsafe to assume that this will succeed
        first, last = fnr2names(person, const, leftpnr[:-1])
        first = transliterate(first) if first else first
        last = transliterate(last) if last else last
        if not (first and last):
            logger.warn("No name information for %s is available. %d "
                        "entry(ies) will be skipped",
                        leftpnr[:-1], len(old_dict[leftpnr]))
            continue

        for entry in old_dict[leftpnr]:
            vals = entry.split(";")
            vals[2] = first
            vals[3] = last
            vals[13] = today
            vals[17] = ""
            # out.write("%s;%s\n" % (leftpnr, ";".join(vals)))
            try:
                out.write("%s;%s\n" % (leftpnr, ";".join(vals)))
            except Exception:
                logger.info('entry=%s', repr(entry))
                logger.info('vals=%s', repr(vals))
                logger.info('leftpnr=%s', repr(leftpnr))
                raise
    out.close()
    newin.close()


def ftpput(host, uname, password, local_dir, file, remote_dir):
    ftp = ftplib.FTP(host, uname, password)
    ftp.cwd(remote_dir)
    ftp.storlines("STOR %s" % file,
                  open(os.path.join(local_dir, file), "r"))
    ftp.quit()


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description='Generates a dump file for the UA database',
    )
    parser.add_argument(
        '-i', '--input-file',
        type=text_type,
        help='system name and input file (e.g. system_sap:/path/to/file)',
    )
    parser.add_argument(
        '-o', '--output-directory',
        type=text_type,
        help='output directory',
    )
    parser.add_argument(
        '-d', '--distribute',
        action='store_true',
        dest='distribute',
        default=False,
        help='upload file (cereconf.UA_*)',
    )
    parser.add_argument(
        '-e', '--employees',
        action='store_true',
        dest='do_employees',
        default=False,
        help='include employees in the output',
    )
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start of %s', parser.prog)
    logger.debug('args: %r', args)

    sysname, person_file = args.input_file.split(":")

    output_file = AtomicFileWriter(
        os.path.join(args.output_directory, "uadata.new"), "w",
        encoding=encoding)

    db = Factory.get("Database")()

    generate_output(db, output_file, args.do_employees, sysname, person_file)
    output_file.close()

    diff_file = "uadata.%s" % time.strftime("%Y-%m-%d")
    do_sillydiff(db, args.output_directory, "uadata.old", "uadata.new",
                 diff_file)
    os.rename(os.path.join(args.output_directory, "uadata.new"),
              os.path.join(args.output_directory, "uadata.old"))

    if args.distribute:
        logger.info('Uploading file to %s', cereconf.UA_FTP_HOST)
        passwd = read_password(cereconf.UA_FTP_UNAME, cereconf.UA_FTP_HOST)
        ftpput(host=cereconf.UA_FTP_HOST,
               uname=cereconf.UA_FTP_UNAME,
               password=passwd,
               local_dir=args.output_directory,
               file=diff_file,
               remote_dir="ua-lt")

    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
