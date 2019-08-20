#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2012 University of Oslo, Norway
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
Email a report of users with ePhorte roles, that has been affiliationless
for N weeks.

"""

import sys
import getopt
from Cerebrum.Utils import Factory
from Cerebrum.utils.email import sendmail
from Cerebrum.modules.no.uio.Ephorte import EphorteRole
from mx import DateTime

logger = Factory.get_logger("cronjob")
db = Factory.get('Database')()
co = Factory.get('Constants')(db)
pe = Factory.get('Person')(db)
ou = Factory.get('OU')(db)
er = EphorteRole(db)



def collect_expired_roles(age):
    """Collectis and returns all roles that belong to people who have had
    their last affiliation from SAP deleted age days ago."""
    now = DateTime.now()
    oldness = now - int(age)

    logger.debug('Collecting expired roles')
    logger.debug('Selecting by affiliation deleted before %s' % str(oldness))

    expired_person_ids = []
    roles = {}
    for row in er.list_roles():
        roles.setdefault(row['person_id'], []).extend([row])

    for p_id in roles.keys():
        exp = True
        for aff in pe.list_affiliations(person_id=p_id,
                                        source_system=co.system_sap,
                                        include_deleted=True):
            if not aff['deleted_date'] or aff['deleted_date'] > oldness:
                exp = False
        
        if exp:
            expired_person_ids.append(p_id)

    for key in roles.keys():
        if not key in expired_person_ids:
            del roles[key]
    
    logger.debug('%d roles collected in %s' % (len(roles),
                                               str(DateTime.now() - now)))
    return roles

def collect_person_names():
    """Collect and return all full names in a dict, indexed by entity_id."""
    start_time = DateTime.now()
    logger.debug('Collecting person names')
    names_by_id = {}
    for row in pe.search_person_names(name_variant=co.name_full,
                                      source_system=co.system_cached):
        names_by_id[row['person_id']] = row['name']
    logger.debug('%d names collected in %s' % (len(names_by_id),
                                              str(DateTime.now() - start_time)))
    return names_by_id

def collect_ansattnr():
    """Collect and return all ansattnrs in a dict, indexed by entity_id."""
    start_time = DateTime.now()
    logger.debug('Collecting all ansattnrs')
    ansattnr_by_id = {}
    for row in pe.search_external_ids(source_system=co.system_sap,
                                      id_type=co.externalid_sap_ansattnr,
                                      fetchall=False):
        ansattnr_by_id[row['entity_id']] = row['external_id']
    logger.debug('%d ansattnrs collected in %s' % (len(ansattnr_by_id),
                                            str(DateTime.now() - start_time)))
    return ansattnr_by_id

def collect_stedkoder():
    """Collect and return all stedkoder in a dict, indexed by entity_id."""
    start_time = DateTime.now()
    logger.debug('Collecting all stedkoder')
    ous = ou.get_stedkoder()
    stedkoder = {}

    for x in ous:
        stedkoder[x['ou_id']] = '%02d%02d%02d' % (x['fakultet'],
                                                  x['institutt'],
                                                  x['avdeling'])
    logger.debug('%d stedkoder collected in %s' % (len(stedkoder),
                                            str(DateTime.now() - start_time)))
    return stedkoder


def format_report(roles, names, ansatt_nr, stedkoder):
    """Generate a report."""
    start_time = DateTime.now()
    logger.debug('Generating report')
    lines = ['%-35s %-10s %-8s %-10s %-8s %s\n' % ('Navn', 'AnsattNr', 'Rolle',
                                              'Journal',  'Stedkode',
                                              'Standardrolle')]
    
    for p_id in roles.keys():
        try:
            l = '%-35s %-10s ' % (names[p_id], ansatt_nr[p_id])
        except KeyError:
            l = '%-35s %-10s ' % (names[p_id], '')

        rs = roles[p_id]
        role = rs.pop(0)
        l += '%-8s %-10s %-8s %s\n' % (str(co.EphorteRole(role['role_type'])),
                            str(co.EphorteJournalenhet(role['journalenhet'])),
                            stedkoder[role['adm_enhet']],
                            role['standard_role'])
        for role in rs:
            l += '%-47s%-8s %-10s %-8s %s\n' % ('',
                            str(co.EphorteRole(role['role_type'])),
                            str(co.EphorteJournalenhet(role['journalenhet'])),
                            stedkoder[role['adm_enhet']],
                            role['standard_role'])
        lines.append(l)
    logger.debug('Report generated in %s' % str(DateTime.now() - start_time))
    return lines


def email_report(to_address, from_address, report):
    """Send the report by email."""
    import smtplib
    try:
        sendmail(to_address, from_address, 'ePhorte role report',
                 report, cc=None)
    except smtplib.SMTPRecipientsRefused, e:
        failed_recipients = e.recipients
        logger.info("Failed to notify <%d> users", len(failed_recipients))
        for email, condition in failed_recipients.iteritems():
            logger.info("Failed to notify: %s", condition)
    except smtplib.SMTPException, msg:
        logger.warn("Error sending to %s: %s" % (to_address, msg))


def usage():
    """Gives user info on how to use the program and its options."""
    print """%s [-htfa]
             -h --help
             -t --to-address example@example.com
             -f --from-address example@example.com
             -a --age Ndays""" % sys.argv[0]


def main(argv=None):
    try:
        opts, args = getopt.getopt(sys.argv[1:], "ht:f:a:",
                                   ["help", "to-address", "from-address",
                                    "age"])
    except getopt.GetoptError:
        usage()
        return 1

    to_addr = from_addr = age = None
    for opt, val in opts:
        if opt in ('-h', '--help',):
            usage()
            return 0
        if opt in ('-t', '--to-address',):
            to_addr = val
        if opt in ('-f', '--from-address',):
            from_addr = val
        if opt in ('-a', '--age',):
            age = val

    if not age:
        age = 28

    # Cache info:
    roles = collect_expired_roles(age)
    names = collect_person_names()
    ansattnr = collect_ansattnr()
    stedkoder = collect_stedkoder()

    rep = format_report(roles, names, ansattnr, stedkoder)

    if to_addr and from_addr:
        email_report(to_addr, from_addr, ''.join(rep))
    else:
        print ''.join(rep)


if __name__ == "__main__":
    main()
