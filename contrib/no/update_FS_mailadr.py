#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2018 University of Oslo, Norway
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

"""Script for updating FS with data from Cerebrum, e.g. mail addresses.

Mail addresses are in FS registered in the database element::

    fs.person.emailadresse

While usernames are registered in:

    fs.person.brukernavn

Addresses of all the persons are first fetched from FS through L{access_FS}.
Currently registered primary address is then compared to the default mailadress
for the primary account the person posesses. If there is a difference between
these two addresses then FS is updated.


Cerebrum could, depending on the instance, be considered as the authoritative
source system in respect to mail addresses and usernames.

As specified by the system owners for FS at the University of Oslo
(representened by SSA, Central student administration) each student
at the University og Oslo has to have a working, official email address
registered in FS (more specifically in the table FS.PERSON, the field
EMAILADRESSE). Any other email addresses (privat email accounts) may be
registered in the field EMAILADRESSE_PRIVAT.

Problems: the addresses fetched from Cerebrum do not take the
account_type nor the source system into consideration. This means that
the default address fetched for a person is the primary address of
that person primary account, not the persons primary student account.
Something should probably be done about this. There is also a number of
users in the Cerebrum database registered with faulty affiliations.
This causes a number of persons to be registered with the addresses
uname@ulrik.uio.no

"""

import sys
import getopt

import cereconf

from Cerebrum import database
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.access_FS import FS


def synchronize_attribute(cerebrum_lookup, fs_lookup, fs_update, index,
                          const, logger, commit_handler):
    """
    Synchronize an attribute A (e-mail or primary account) between Cerebrum
    and FS.  Attribute A's value MUST be unique (or Null).

    CEREBRUM_LOOKUP is a function yielding a mapping between no_ssn and A
    from Cerebrum.

    FS_LOOKUP is a function yielding a mapping between no_ssn and A from FS.

    FS_UPDATE is a function that update A's value for a given no_ssn in FS.
    """

    logger.debug("Fetching information from Cerebrum")
    fnr2attribute = cerebrum_lookup(const.externalid_fodselsnr)
    logger.debug("Done fetching information from Cerebrum")
    updates = {}
    additions = {}

    for row in fs_lookup():
        fnr = "%06d%05d" % (int(row['fodselsdato']), int(row['personnr']))
        cere_attribute = fnr2attribute.get(fnr, None)
        fs_attribute = row[index]

        logger.debug3("Considering %s for %s: cerebrum:%s fs:%s",
                      index, fnr, cere_attribute, fs_attribute)

        # Cerebrum has a record of this fnr
        if cere_attribute is not None:
            if fs_attribute is None:
                logger.debug1("Will add %s for %s: %s",
                              index, fnr, cere_attribute)
                additions[cere_attribute] = [row['fodselsdato'],
                                             row['personnr']]
            # We update only when the values differ, but we can't do
            # it here since FS may have a uniqueness constraint, and
            # an update could then lead to two entries temporarily
            # having the same value.
            elif cere_attribute != fs_attribute:
                logger.debug1("Will update %s: %s -> %s",
                              fnr, fs_attribute, cere_attribute)
                updates[fs_attribute] = [row['fodselsdato'], row['personnr'],
                                         cere_attribute]

        # Attribute registered in FS does not exist in Cerebrum anymore
        else:

            if fs_attribute is not None:
                logger.info("Deleting %s for %s: %s",
                            index, fnr, fs_attribute)

                # None in FS means "no value"
                fs_update(row['fodselsdato'], row['personnr'], None)
                commit_handler()

    for fs_value in updates.keys():
        # Have we already done this update?
        if updates[fs_value] is None:
            continue

        fdato, persnr, cere_value = updates[fs_value]

        # Does the value we're changing to exist in FS already?  If
        # so, change the person having that value first.  This should
        # be a recursive function, but cascading changes probably
        # don't happen in practice.  Update the other

        if cere_value in updates:
            u_fs_value = cere_value
            u_fdato, u_persnr, u_cere_value = updates[u_fs_value]
            logger.info("Changing cascading %s for %06d%05d: %s -> %s",
                        index, u_fdato, u_persnr, u_fs_value, u_cere_value)
            fs_update(u_fdato, u_persnr, u_cere_value)
            commit_handler()
            # Mark it as done
            updates[cere_value] = None

        logger.info("Changing %s for %06d%05d: %s -> %s",
                    index, fdato, persnr, fs_value, cere_value)
        try:
            fs_update(fdato, persnr, cere_value)
            commit_handler()
        except Exception as e:
            logger.error("Failed updating %s for %06d%05d to %s: %s",
                         index, fdato, persnr, cere_value, e)

    # Now all old values are cleared away, and adding values to new(?)
    # persons can't give duplicates.

    for cere_value in additions.keys():
        fdato, persnr = additions[cere_value]
        logger.info("Adding %s for %06d%05d: %s",
                    index, fdato, persnr, cere_value)
        try:
            fs_update(fdato, persnr, cere_value)
            commit_handler()
        except Exception as e:
            logger.error("Failed adding %s for %06d%05d to %s: %s",
                         index, fdato, persnr, cere_value, e)

    logger.debug("Done updating attributes")


def usage(exitcode=0):
    print("""
%(doc)s

Usage: update_FS_mailadr.py [options]

-e --email           Synchronize e-mail information
-a --account         Synchronize account information
-u --db-user NAME    Connect with given database username
-s --db-service NAME Connect to given database
-d --dryrun          Run synchronization, but do *not* update FS

""" % {'doc': __doc__})
    sys.exit(exitcode)


def main():
    logger = Factory.get_logger("cronjob")
    logger.info("Synchronizing FS with Cerebrum")

    try:
        opts, args = getopt.getopt(
            sys.argv[1:],
            "hdu:s:ea",
            ["help", "dryrun", "db-user=", "db-service=", "email", "account"])
    except getopt.GetoptError as e:
        print(e)
        usage(2)

    user = "I0185_ureg2000"
    service = "fsprod.uio.no"
    dryrun = False
    email = False
    account = False

    for option, value in opts:
        if option in ('-d', '--dryrun'):
            dryrun = True
        elif option in ('-u', '--db-user',):
            user = value
        elif option in ('-s', '--db-service',):
            service = value
        elif option in ('-e', '--email',):
            email = True
        elif option in ('-a', '--account'):
            account = True
        elif option in ('-h', '--help'):
            usage()
        else:
            print("Unknown argument: %s" % option)
            usage(2)

    DB_driver = getattr(cereconf, 'DB_DRIVER_ORACLE', 'cx_Oracle')
    fs_db = database.connect(user=user, service=service, DB_driver=DB_driver)
    fs = FS(fs_db)

    db = Factory.get('Database')()
    person = Factory.get('Person')(db)
    const = Factory.get('Constants')(db)

    if dryrun:
        logger.info('This is a dryrun, changes will be rolled back')
    else:
        logger.info('Not a dryrun, changes will be committed')

    def commit_handler():
        if dryrun:
            fs.db.rollback()
            logger.info("Rolled back all changes")
        else:
            fs.db.commit()
            logger.info("Committed all changes")

    if email:
        synchronize_attribute(person.getdict_external_id2mailaddr,
                              fs.person.list_email,
                              fs.person.write_email,
                              "emailadresse", const, logger, commit_handler)

    if account:
        synchronize_attribute(person.getdict_external_id2primary_account,
                              fs.person.list_uname,
                              fs.person.write_uname,
                              "brukernavn", const, logger, commit_handler)


if __name__ == '__main__':
    main()
