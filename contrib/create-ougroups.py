#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016 University of Oslo, Norway
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
"""Generate OU groups based on config file.

Example config (JSON with comments):
{
    "types": [
    {
        // name given as arg to script
        "name": "test",
        // List of OU roots
        "root": ["900199"],
        // OU group type
        "recursion": "recursive",
        // OU membership type
        "members": "primary_account",
        // Affiliation + status
        "aff": "STUDENT/aktiv",
        // Source system
        "source": "FS",
        // Add these spreads to group
        "spreads": ["exch_group@uio"],
        // OU perspective
        "perspective": "SAP",
        // Name given to group. Replaces {} with six digit stedkode
        "nametemplate": "student-{}",
        // Description of group. Replaces {} with stedkode
        "descriptiontemplate": "Studenter ved {}"
    },
    {
        "name": "test-more",
        …
    }
    ]
}

"""

import sys
import argparse

import cereconf
from Cerebrum.config.configuration import (ConfigDescriptor,
                                           Configuration,
                                           Namespace)
from Cerebrum.config.settings import (Iterable,
                                      Choice,
                                      String)
from Cerebrum.Utils import Factory
from Cerebrum.config.loader import read, read_config


class TypeConfig(Configuration):
    """Describes the types sent as argument"""

    name = ConfigDescriptor(String,
                            doc=u'This type name, given as parameter to script')

    root = ConfigDescriptor(Iterable,
                            template=String(),
                            doc=u'The roots for insertion (stedkode)')

    recursion = ConfigDescriptor(
        Choice,
        choices=set(('recursive', 'flattened', 'nonrecursive')),
        doc=u'The recursion type for this ougroups')

    members = ConfigDescriptor(
        Choice,
        choices=set(('person', 'primary_account', 'account')),
        doc=u'The membership type for this ougroups')

    aff = ConfigDescriptor(
        String,
        doc=u'The affiliation for this (e.g. STUDENT/aktiv)')

    source = ConfigDescriptor(
        String,
        doc=u'The source system of affiliations')

    spreads = ConfigDescriptor(
        Iterable,
        template=String(),
        doc=u'Spreads added to groups')

    perspective = ConfigDescriptor(
        String,
        doc=u'Perspective code for new groups')

    nametemplate = ConfigDescriptor(
        String,
        doc=u'Name for groups. Use {} to insert stedkode')

    descriptiontemplate = ConfigDescriptor(
        String,
        doc=u'Description for groups. Use {} to insert stedkode')


class CreateOuGroupConfig(Configuration):

    types = ConfigDescriptor(
        Iterable,
        template=Namespace(config=TypeConfig))


logger = Factory.get_logger('cronjob')


def parse_aff(aff, co):
    """Parse 'foo/bar' as aff = foo and status = bar"""
    if '/' in aff:
        aff, status = aff.split('/')
        aff = co.PersonAffiliation(aff)
        status = co.PersonAffStatus(aff, status)
    else:
        aff = co.PersonAffiliation(aff)
        status = None
    return aff, status


def parse_sko(sko):
    """Convert sko into a tuple for mod_stedkode"""
    assert len(sko) == 6 and sko.isdigit()
    sko = map(int, (sko[0:2], sko[2:4], sko[4:6]))
    sko.append(cereconf.DEFAULT_INSTITUSJONSNR)
    return sko


def emit_sko(ou):
    """Get stedkode in the normal six digit format"""
    return ('{:02d}' * 3).format(ou.fakultet, ou.institutt, ou.avdeling)


def setup_types(db, root, recursion, aff, status, source, members, perspective,
                template, description, spreads, co):
    """Setup ou groups for root and below"""
    global logger
    logger.info("Setting up groups in %s (perspective=%s)", root, perspective)
    ou = Factory.get('OU')(db)
    gr = Factory.get('Group')(db)
    ac = Factory.get('Account')(db)
    ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    ou.find_stedkode(*parse_sko(root))
    ous = set([ou.entity_id])
    ous.update([x['ou_id'] for x in ou.list_children(perspective,
                                                     recursive=True)])
    for ouid in ous:
        ou.clear()
        ou.find(ouid)
        sko = emit_sko(ou)
        logger.info("Checking for %s", sko)
        name = template.format(sko)
        desc = description.format(sko)
        try:
            gr.find_by_name(name)
            logger.info("Group %s exists", name)
        except:
            logger.info("Creating new group %s", name)
            gr.populate(visibility=co.group_visibility_all, name=name,
                        description=desc, group_type='ougroup',
                        ou_id=ou.entity_id, affiliation=aff,
                        affiliation_source=source, affiliation_status=status,
                        recursion=recursion, ou_perspective=perspective,
                        member_type=members, creator_id=ac.entity_id)
            gr.write_db()
        for spread in spreads:
            if not gr.has_spread(spread):
                logger.info("Adding spread %s", str(spread))
                gr.add_spread(spread)
        gr.clear()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-c', '--commit', action='store_true',
                        default=False, help="Do commit the changes to db")
    parser.add_argument('--config', action='store', default=None,
                        help='Config file')
    parser.add_argument('types', action='store', nargs='+',
                        help='The types to create (see config)')
    args = parser.parse_args()

    if args.config:
        conf = CreateOuGroupConfig(read_config(args.config))
    else:
        conf = read(CreateOuGroupConfig(), 'create-ougroups')

    configs = {}
    for t in conf.types:
        configs[t.name] = t

    db = Factory.get('Database')(client_encoding='UTF-8')
    db.cl_init(change_program="create-ougroups")
    co = Factory.get('Constants')(db)

    for tp in args.types:
        if tp in configs:
            logger.info('Setting up groups for rule %s', tp)
            conf = configs[tp]
            aff, status = parse_aff(conf.aff, co)
            source = co.AuthoritativeSystem(conf.source)
            roots = conf.root
            recursion = co.VirtualGroupOURecursion(conf.recursion)
            members = co.VirtualGroupOUMembership(conf.members)
            perspective = co.OUPerspective(conf.perspective)
            spreads = map(co.Spread, conf.spreads)
            for root in roots:
                logger.info('Setting up root %s', root)
                setup_types(db, root, recursion, aff, status, source, members,
                            perspective, conf.nametemplate,
                            conf.descriptiontemplate, spreads, co)
            logger.info('Done setting up %s', tp)
        else:
            sys.exit(1)
    if args.commit:
        logger.info('Committing')
        db.commit()
    else:
        logger.info('Doing rollback')
        db.rollback()

if __name__ == '__main__':
    main()
