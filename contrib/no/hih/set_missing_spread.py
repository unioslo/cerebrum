#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2009-2015 University of Oslo, Norway
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
Usage: set_missing_spread.py [options]
-s --spread <spread>   Set the spread <spread>
--ufile <file>         Add spread to the users in <file>
--gfile <file>         Add spread to the groups in <file>
--group <group>        Add spread to the group <group>
-a --aff <affiliation> Affiliation to set spread on
-u --user <uname>      Add spread to the user <uname>
--person               Add spreads to persons
--commit               Run in commit-mode
-h --help              This help text
"""

import sys
import getopt
import cerebrum_path
getattr(cerebrum_path, "linter", "should be silent!")

from Cerebrum import Errors
from Cerebrum.Utils import Factory

logger = Factory.get_logger("console")
db = Factory.get('Database')()
db.cl_init(change_program='fix_spreads')
constants = Factory.get('Constants')(db)


def usage(msg, exit_status):
    """Gives user info on how to use the program and its options."""
    if msg:
        print >>sys.stderr, "\n%s" % msg
    print >>sys.stderr, __doc__

    sys.exit(exit_status)


def add_spread(entities, spread, entity_type='user'):
    if entity_type == 'user':
        ent = Factory.get('Account')(db)
    elif entity_type == 'group':
        ent = Factory.get('Group')(db)
    elif entity_type == 'person':
        ent = Factory.get("Person")(db)
    for e in entities:
        try:
            ent.clear()
            ent.find_by_name(e)
            if ent.has_spread(spread):
                logger.debug("%s already has spread %s", entity_type, spread)
                continue
            ent.add_spread(spread)
            logger.debug("Added spread %s for %s %s", spread, entity_type, e)
            ent.write_db()
        except Errors.NotFoundError:
            logger.warn("Couldn't find %s %s", entity_type, e)
        except Exception, msg:
            logger.error("Couldn't set spread %s for %s %s:\n%s",
                         spread, entity_type, e, msg)


def add_spread_aff_based(affs, spread, entity_type):
    if entity_type == 'user':
        ac = Factory.get('Account')(db)
    elif entity_type == 'person':
        person = Factory.get('Person')(db)
    for aff in affs:
        logger.debug("Handling affiliation %s", aff)
        aff = getattr(constants, aff)
        if entity_type == 'user':
            for row in ac.list_accounts_by_type(affiliation=aff):
                try:
                    ac.clear()
                    ac.find(row['account_id'])
                    logger.debug3("Checking %s", ac.account_name)
                    if not ac.has_spread(spread):
                        ac.add_spread(spread)
                        ac.write_db()
                        logger.debug("Added spread %s for %s", spread,
                                     ac.account_name)
                except Errors.NotFoundError:
                    logger.warn("Couldn't find account %s", row['account_id'])
                except Exception, msg:
                    logger.error("Couldn't set spread %s for %s %s:\n%s",
                                 spread, row['account_id'], msg)
        elif entity_type == 'person':
            for row in person.list_affiliations(affiliation=aff):
                try:
                    person.clear()
                    person.find(row['person_id'])
                    if not person.has_spread(spread):
                        person.add_spread(spread)
                        person.write_db()
                        logger.debug("Added spread %s for %s", spread,
                                     row['person_id'])
                except Errors.NotFoundError:
                    logger.warn("Couldn't find person %s", row['person_id'])
                except Exception, msg:
                    logger.error("Couldn't set spread %s for %s %s:\n%s",
                                 spread, row['person_id'], msg)


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'f:u:g:s:a:h',
                                   ['spread=', 'uname=', 'group=',
                                    'ufile=', 'gfile=', 'aff=',
                                    'person', 'commit', 'help'])
    except getopt.GetoptError:
        logger.error("Argument error")
        sys.exit(1)

    spread = None
    commit = False
    filename = None
    entities = []
    affs = []
    entity_type = 'user'
    for opt, val in opts:
        if opt in ('-s', '--spread'):
            try:
                spread = getattr(constants, val)
            except:
                logger.error("No such spread: %s", val)
                sys.exit(1)
        elif opt in ('--commit',):
            commit = True
        elif opt in ('--ufile',):
            filename = val
            entity_type = 'user'
        elif opt in ('--gfile',):
            filename = val
            entity_type = 'group'
        elif opt in ('-u', '--uname'):
            entities.append(val)
            entity_type = 'user'
        elif opt in ('-g', '--group'):
            entities.append(val)
            entity_type = 'group'
        elif opt in ('-a', '--aff'):
            affs.append(val)
        elif opt in ('--person',):
            entity_type = 'person'
        elif opt in ('-h', '--help'):
            usage(None, 0)

    if not spread:
        usage("No spread given", 2)

    if filename:
        try:
            f = open(filename)
            entities.extend([x.strip() for x in f.readlines()])
            f.close()
        except IOError, e:
            logger.error("Couldn't open file %s, %s", val, str(e))
        except:
            logger.error("Ops!")

    if entities:
        add_spread(entities, spread, entity_type=entity_type)
    elif affs:
        add_spread_aff_based(affs, spread, entity_type)
    else:
        usage("No affs, users or groups given", 3)

    if commit:
        logger.info("Committing all changes")
        db.commit()
    else:
        logger.info("Rolling back all changes")
        db.rollback()

if __name__ == '__main__':
    main()
