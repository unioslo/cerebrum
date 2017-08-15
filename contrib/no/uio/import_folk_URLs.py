#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2004 University of Oslo, Norway
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

"""Usage: import_folk_URLs.py [--max-change=<percentage> | --force]

Maintain home pages in entity_contact_info for persons:
Source system 'folk.uio.no', concact type 'URL', entity type 'person'.

Options:
    --max-change=<percentage>   Max acceptable percentage for change
                                in number of persons with a home page,
                                unless the database has no home pages.
    --force             Same as --max-change=100 --logger-name=console."""

# The code wastes some time in order to use the standard API:
# - populate_contact_info()+write_db() reads URLs for each person
#   even though list_contact_info() already has read them all.
# - Each person.find() does two SELECTs which the program does not need.

import getopt
import re
import sys
import urllib

import cerebrum_path
from Cerebrum.Utils import Factory


# List of users who have home pages.  One user per line.
# Generated by www-drift@usit.uio.no.
source_URL = "http://folk.uio.no/brukere.txt"

# Convert user name to home page URL at UiO
def user2URL(user): return "http://folk.uio.no/%s/" % (user,)

# Verify user name
check_user_name = re.compile(r"[a-z][a-z0-9_-]+\Z", re.I).match

# Default max change in percent in number of persons who has a home page
max_change = 5


def main():
    global max_change
    logger = Factory.get_logger(
        "--force" in sys.argv and "console" or "cronjob")
    try:
        opts, args = getopt.getopt(sys.argv[1:], "", ("force", "max-change="))
    except getopt.GetoptError, e:
        usage(str(e))
    if args:
        usage("Invalid arguments: " + " ".join(args))
    for opt, val in opts:
        max_change = (opt == "--force" and 100 or int(val))

    home_page_users = {}        # {user who has a home page: True}
    try:
        act = "open"
        conn = urllib.URLopener({}).open(source_URL)
        act = "check"
        actual_URL = conn.geturl()
        if actual_URL != source_URL:
            sys.exit("Error: Unexpected redirection to <%s>." % (actual_URL,))
        act = "read"
        for user in conn.readlines():
            user = user.rstrip("\r\n")
            if not check_user_name(user):
                sys.exit("Bad user name '%s' in <%s>." % (user, actual_URL))
            home_page_users[user] = True
        act = "close"
        conn.close()
    except EnvironmentError, e:
        sys.exit("%s(%s) failed: %s." % (act, source_URL, e.strerror))

    db = Factory.get('Database')()
    db.cl_init(change_program='import_folk_URLs')
    co = Factory.get('Constants')(db)
    account = Factory.get('Account')(db)
    person = Factory.get('Person')(db)

    id2acc = {}                 # {account_id: user name}
    for row in account.list_names(co.account_namespace):
        id2acc[int(row['entity_id'])] = row['entity_name']

    person2URLs = {}            # {person_id: [desired URL, ...]}
    for row in account.list_accounts_by_type():
        account_id = int(row['account_id'])
        user = id2acc.get(account_id)
        if user in home_page_users:
            del home_page_users[user]
            person2URLs.setdefault(int(row['person_id']), []).append(
                user2URL(user))

    del home_page_users, id2acc, account  # Release some memory

    has_old_URL = {}            # {person_id who has URL in database: True}
    for row in person.list_contact_info(source_system=co.system_folk_uio_no,
                                        contact_type=co.contact_url,
                                        entity_type=co.entity_person):
        has_old_URL[int(row['entity_id'])] = True

    old_count = len(has_old_URL)
    new_count = len(person2URLs)
    if max_change < 100:
        if old_count != 0 and abs(100*new_count//old_count - 100) > max_change:
            sys.exit("""
Exiting, too big change in number of people with home pages: %d -> %d.
Use the '--force' argument to force this change."""
                     % (old_count, new_count))
    logger.info("DB had %d URLs, will have %d URLs." % (new_count, old_count))

    # Insert person2URLs in database; delete them from variable has_old_URL
    for person_id, new in person2URLs.iteritems():
        person.clear()
        person.find(person_id)
        for pref, URL in zip(xrange(1, len(new) + 1), new):
            person.populate_contact_info(co.system_folk_uio_no,
                                         co.contact_url, URL, pref)
        person.write_db()
        if person_id in has_old_URL:
            del has_old_URL[person_id]
    person2URLs = None

    # Delete remaining URLs from database
    for person_id in has_old_URL:
        person.clear()
        person.find(person_id)
        person.delete_contact_info(source=co.system_folk_uio_no,
                                   contact_type=co.contact_url)

    db.commit()


def usage(msg):
    sys.exit("%s\n%s" % (msg, __doc__))


if __name__ == '__main__':
    main()

