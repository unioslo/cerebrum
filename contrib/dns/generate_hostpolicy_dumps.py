#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
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
"""Script for generating the various hostpolicy csv files that is related to
cfengine. It can be specified what files to generate. The documentation about
the hostpolicies are located at:

    https://usit.uio.no/om/tjenestegrupper/cerebrum/dokumentasjon/ekstern/uio/dns/

There are four different files:

    atoms.csv: one atom per line, on the format:

        - atomname;description;foundation;date

    roles.csv: one role per line, on the format:

        rolename;description;foundation;date;members*

        - The members are listed by their entity_names and are separated by commas.

    hostpolicies.csv: one host per line, on the format:

        hostnavn;policy+

        - Hosts without roles/atoms is not included.

        - Only policies that are directly assosiacte are included.

        - Policies are comma separated.

    policyrelationships.csv: one relationship per line, on the format:

        source_policy_name;relationship_code_str;target_policy_name

The date format is: YYYY-MM-DD
"""

import sys, os, getopt
from mx import DateTime

import cerebrum_path, cereconf
from Cerebrum.Utils import Factory
from Cerebrum.modules.hostpolicy.PolicyComponent import Atom, Role

logger = Factory.get_logger('cronjob')

def usage(exitcode=0):
    print """Usage: %(filename)s [options]

    %(doc)s
    
    Options:

    --atoms FILE            The file to put all atoms in.

    --roles FILE            The file to put all roles in.

    --hostpolicies FILE     The file to put all host with their policies in.

    --relationships FILE    The file to put all relationships in.


    --help                  Show this and quit.
    """ % {'filename': os.path.basename(sys.argv[0]),
           'doc': __doc__}
    sys.exit(exitcode)

def process_atoms(stream):
    """Go through all atoms in the database and send them to the stream."""
    logger.info('process_atoms started')
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    atom = Atom(db)
    for row in atom.search():
        stream.write(';'.join((row['entity_name'],
                               row['description'],
                               row['foundation'], 
                               row['create_date'].strftime('%Y-%m-%d'))))
        stream.write('\n')
    logger.info('process_atoms done')

def process_roles(stream):
    logger.info('process_roles started')
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    role = Role(db)
    for row in role.search():
        stream.write(';'.join((row['entity_name'],
                               row['description'],
                               row['foundation'], 
                               row['create_date'].strftime('%Y-%m-%d'))))
        stream.write('\n')
    logger.info('process_roles done')

def process_hostpolicies(stream):
    logger.info('process_hostpolicies started')
    # TODO
    logger.info('process_hostpolicies done')

def process_relationships(stream):
    logger.info('process_relationships started')
    # TODO
    logger.info('process_relationships done')

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'h',
                ['atoms=', 'roles=', 'hostpolicies=', 'relationships='])
    except getopt.GetoptError, e:
        print e
        usage(1)

    atomstream = rolestream = hostpolicystream = relationshipstream = None

    for opt, arg in opts:
        if opt in ('-h', '--help'):
            usage()
        elif opt == '--atoms':
            atomstream = open(arg, 'w')
        elif opt == '--roles':
            rolestream = open(arg, 'w')
        elif opt == '--hostpolicies':
            hostpolicystream = open(arg, 'w')
        elif opt == '--relationships':
            relationshipstream = open(arg, 'w')
        else:
            print "Unknown argument: %s" % opt
            usage(1)

    action = False
    for stream, process in ((atomstream, process_atoms),
                            (rolestream, process_roles),
                            (hostpolicystream, process_hostpolicies),
                            (relationshipstream, process_relationships)):
        if stream is not None:
            process(stream)
            stream.close()
            action = True
    if not action:
        print 'No dump specified, got nothing to do'
        usage(1)

if __name__ == '__main__':
    main()

