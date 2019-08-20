#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2002-2017 University of Oslo, Norway
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
""" Export data in .xml format to be imported into TROFAST systems

See http://www.uninett.no/trofast/Integrasjon/brukerdadm.html for details
Note: The spec states that 'initial' attribute can't be equal to uid part of
      Feide id. This script does not (currently) follow that rule, and
      Uninett has stated that it's not required.
"""
import argparse

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import Stedkode
from Cerebrum.Utils import XMLHelper
from Cerebrum.utils.atomicfile import MinimumSizeWriter


logger = Factory.get_logger("cronjob")

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
ou = Factory.get('OU')(db)
person = Factory.get('Person')(db)
stedkode = Stedkode.Stedkode(db)
account = Factory.get('Account')(db)


KiB = 1024
MiB = KiB**2


def get_person_oudisp(person):
    affs = person.get_affiliations()
    for aff in affs:
        stedkode.clear()
        stedkode.find(aff['ou_id'])
    return stedkode.name


def export_account(f, account_id):
    account.clear()
    account.find(account_id)

    person.clear()
    person.find(account.owner_id)

    last = first = None
    try:
        first = person.get_name(co.system_cached, co.name_first)
        last = person.get_name(co.system_cached, co.name_last)
        full = person.get_name(co.system_cached, co.name_full)
    except Errors.NotFoundError:
        pass
    fnr = None
    studentnr = None
    for rr in person.get_external_id(id_type=co.externalid_fodselsnr):
        fnr = rr['external_id']
    for rr in person.get_external_id(id_type=co.externalid_studentnr):
        studentnr = rr['external_id']
    try:
        (mailuser, domain) = account.get_primary_mailaddress().split('@')
    except:
        return
    # sted = get_person_oudisp(person)
    f.write(("<personid personidtype=\"feide\">%s@%s</personid>\n") %
            (account.account_name, domain))
    f.write(("<personid personidtype=\"initial\">%s</personid>\n") %
            (account.account_name))
    f.write(("<personid personidtype=\"NationalIdNr\">%s</personid>\n") % fnr)
    if studentnr is not None:
        f.write(("<personid personidtype=\"student id\">%s</personid>\n") %
                studentnr)
    f.write(("<personid personidtype=\"userid\">%s</personid>\n") %
            account.account_name)
    f.write(("<personid personidtype=\"initial\">%s</personid>\n") %
            account.account_name)

    f.write("<name>\n<n>\n")
    if full is not None:
        f.write("<fn>%s</fn>\n" % full)
    if last is not None:
        f.write("<family>%s</family>\n" % last)
    if first is not None:
        f.write("<given>%s</given>\n" % first)
    f.write("</n>\n</name>\n")
#    TODO: Export primary affiliation, Steinar K.
#    f.write("<Affiliation></Affiliation>\n")
    f.write("<contactinfo contacttype=\"email\">%s@%s</contactinfo>\n" %
            (mailuser, domain))


def ephorte_export(spread_id, filename):
    xml = XMLHelper()
    with MinimumSizeWriter(filename) as f:
        f.min_size = 1 * MiB
        ou.clear()
        ou.find(int(ou.root()[0]['ou_id']))
        f.write(xml.xml_hdr + "<persons>\n")
        f.write("<orgid>%s</orgid>\n" % ou.get_language_with_name(
            co.ou_name_acronym, co.language_nb).lower())
        for row in account.list_all_with_spread(spread_id):
            f.write("<person>\n")
            export_account(f, row['entity_id'])
            f.write("</person>\n")
        f.write("</persons>\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-o', '--output-file',
        required=True,
        dest='filename',
        metavar="FILE",
        help="Write XML dump to %(metavar)s")
    parser.add_argument(
        '-s', '--spread',
        required=True,
        metavar="STRVAL",
        help="The ephorte account spread value to export")
    args = parser.parse_args()

    logger.info("Starting ephorte_dump")

    spread = co.human2constant(args.spread, co.Spread)
    if spread is None:
        raise SystemExit("Spread not found ({!r})".format(args.spread))
    if spread.entity_type is not co.entity_account:
        raise SystemExit("Spread must be an account spread.")
    ephorte_export(int(spread), args.filename)


if __name__ == '__main__':
    main()
