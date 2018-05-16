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
"""
Convert affiliation events to group events

Since OU groups are synthesized based on the affiliations given to a user,
group events needs to be added based on changes in affiliations (and account
types). This script should be run periodically, and generally after jobs
changing affiliations.
"""

import argparse
from Cerebrum.Utils import Factory
from Cerebrum.utils import json
from Cerebrum.modules import CLHandler
from Cerebrum.Errors import NotFoundError

logger = None
EVENT_KEY = 'ou-group'


"""
Why this script? Generating these events can require some computation from the
database and API. It would make a lot of such scripts using this API slow. Also,
we can assume several changes occur at once, so it should be possible to perform
better by doing required computations once.

This script reads through change events and generates group events for OU
groups. The OU groups will, however, also generate such events upon creation
and destruction, as these can be generated reasonably fast on the fly.
"""


def make_data():
    """Create data object"""
    return {
        'person': {},
        'account': {},
        'replay': set(),
        'ignoregroups': set(),
    }


def key(ou_id=None, affiliation=None, status=None, source=None):
    """Create a key for affiliation source"""
    return (ou_id, affiliation, status, source)


def fill_person(pid, db, co, data):
    """Look up a person and put info into data.

    fills data['person'][$id] with
    old = { 'account': prioritized list of account type,
            'personal': key → set of group ids,
            'primary': key → set of group ids
    }
    new = { 'account': current primary account id,
            'personal': set of group ids,
            'primary': set of group ids
    }

    Both old and new is filled with current data, but old should be updated
    by looking through change log.
    """
    p = Factory.get('Person')(db)
    p.find(pid)
    a = Factory.get('Account')(db)
    ats = a.get_account_types(owner_id=pid)
    if ats:
        primary_account = [(at['account_id'], at['priority'], at['ou_id'],
                            at['affiliation']) for at in ats]
    else:
        primary_account = []
    old = {
        # Find change in primary account → primary groups
        'account': primary_account,
        # Groups where person is member
        'personal': {},
        # Groups where primary account is member
        'primary': {},
    }
    affs = p.list_affiliations(person_id=pid)
    g = Factory.get('Group')(db)
    personal = set()
    primary = set()
    for aff in affs:
        pers = g.list_ou_groups_for(aff['ou_id'],
                                    affiliation=aff['affiliation'],
                                    status=aff['status'],
                                    source=aff['source_system'],
                                    member_types=co.virtual_group_ou_person,
                                    indirect=False)
        dct = old['personal']
        k = key(aff['ou_id'], aff['affiliation'], aff['status'],
                aff['source_system'])
        tmp = dct[k] = set()
        for gid in (int(x['group_id']) for x in pers):
            if gid not in data['ignoregroups']:
                tmp.add(gid)
                personal.add(gid)

        prim = g.list_ou_groups_for(aff['ou_id'],
                                    affiliation=aff['affiliation'],
                                    status=aff['status'],
                                    source=aff['source_system'],
                                    member_types=co.virtual_group_ou_primary,
                                    indirect=False)
        dct = old['primary']
        tmp = dct[k] = set()
        for gid in (int(x['group_id']) for x in prim):
            if gid not in data['ignoregroups']:
                tmp.add(gid)
                primary.add(gid)
    ret = {
        'old': old,
        'new': {
            'account': primary_account[0] if primary_account else None,
            'personal': personal,
            'primary': primary,
        },
        'ignoregroups': data['ignoregroups'],
    }
    data['person'][pid] = ret
    return ret


def fill_account(acct, db, co, data):
    """Look up account and fill data

    data should contain:
    old = key → set of group ids
    new = set of group ids
    owner = owner id
    """
    g = Factory.get('Group')(db)
    a = Factory.get('Account')(db)
    a.find(acct)
    ats = a.get_account_types()
    own = data['person'].get(a.owner_id)
    if own is None:
        own = fill_person(a.owner_id, db, co, data)
    ret = {
        'old': {},
        'new': set(),
        'owner': own,
        'ignoregroups': data['ignoregroups'],
    }
    for at in ats:
        grps = g.list_ou_groups_for(at['ou_id'], affiliation=at['affiliation'],
                                    member_types=co.virtual_group_ou_accounts,
                                    indirect=False)
        k = key(at['ou_id'], at['affiliation'])
        dct = ret['old'][k] = set()
        for gid in (int(x['group_id']) for x in grps):
            if gid not in data['ignoregroups']:
                dct.add(gid)
                ret['new'].add(gid)
    data['account'][acct] = ret
    return ret


def handle_person_aff_add(event, db, co, data, p):
    """Handle person_aff_src_add"""
    if p is None:  # Old event
        return

    # change_params: ou_id, affiliation, source, status
    # Delete resulting groups from old side of data.
    k = key(p['ou_id'], p['affiliation'], p['status'], p['source'])
    del data['old']['primary'][k]
    del data['old']['personal'][k]


def person_addold(db, co, data, ou, aff, status, src):
    """Helper to add old groups to data."""
    # This should most of the time generate new groups in old, not found
    # in new, thus generating group rem events.
    o = key(ou, aff, status, src)
    grp = Factory.get('Group')(db)
    gs = grp.list_ou_groups_for(ou, affiliation=aff, status=status, source=src,
                                member_types=co.virtual_group_ou_person,
                                indirect=False)
    dct = data['old']['personal'][o] = set()
    for g in gs:
        if int(g['group_id']) not in data['ignoregroups']:
            dct.add(int(g['group_id']))
    gs = grp.list_ou_groups_for(ou, affiliation=aff, status=status, source=src,
                                member_types=co.virtual_group_ou_primary,
                                indirect=False)
    dct = data['old']['primary'][o] = set()
    for g in gs:
        if int(g['group_id']) not in data['ignoregroups']:
            dct.add(g['group_id'])


def handle_person_aff_mod(event, db, co, data, p):
    """Handle person_aff_src_mod"""
    logger.debug('handle_person_aff_mod called')
    if p is None:  # Old event
        return

    # change_params: oldstatus + add params
    # Should work as a combined add and del.
    n = key(p['ou_id'], p['affiliation'], p['status'], p['source'])
    del data['old']['personal'][n]
    del data['old']['primary'][n]
    person_addold(db, co, data, p['ou_id'], p['affiliation'], p['oldstatus'],
                  p['source'])


def handle_person_aff_del(event, db, co, data, p):
    """Handle person_aff_src_del"""
    logger.debug('handle_person_aff_del called')
    if p is None:  # Old event
        return

    # change_params: ou_id, affiliation, source (status)
    # if only source is set, all affs are nuked
    if 'ou_id' not in p:
        # TODO: reconstruct for source (probably no groups)
        logger.error('person.nuke_affiliation_for_source_system({source}) '
                     'called for id:{pid}. Manual fix needed?',
                     source=p['sourcestr'], pid=event['subject_entity'])
    else:
        person_addold(db, co, data, p['ou_id'], p['affiliation'],
                      p['status'], p['source'])


def handle_account_type_add(event, db, co, data, p):
    """Handle account_type_add"""
    logger.debug('handle_account_type_add called')
    # Delete matches from old. Will often generate group_add
    # Additionally, might trigger change in primary account.
    ou, affiliation, priority = p['ou_id'], p['affiliation'], p['priority']
    k = key(ou, affiliation)
    if k in data['old']:
        del data['old'][k]
    lst = data['owner']['old']['account']
    logger.debug('before %s', lst)
    for i, item in enumerate(lst):
        if item[1] == priority:
            del lst[i]
            break
    logger.debug('after %s', lst)


def handle_account_type_mod(event, db, co, data, p):
    """Handle account_type_mod"""
    logger.debug('handle_account_type_mod called')
    # change_params: new_pri, old_pri
    # Combined add + del
    new, old = p['new_pri'], p['old_pri']
    lst = data['owner']['old']['account']
    accid = event['subject_entity']
    logger.debug('before %s', lst)
    for i, item in enumerate(lst):
        if item[1] == new:
            # assert item[0] == event['subject_entity']
            accid, new, ou, aff = item
            del lst[i]
            break
    else:
        logger.error('Account type for priority %s not found for id:%s, '
                     'skipping', new, accid)
        return
    for i, item in enumerate(lst):
        if old < item[1]:
            lst.insert(i, (accid, old, ou, aff))
            break
    else:
        lst.append((accid, old, ou, aff))
    logger.debug('after %s', lst)


def handle_account_type_del(event, db, co, data, p):
    """Handle account_type_del"""
    logger.debug('handle_account_type_del called')
    # 1. Add matches to old.
    # 2. Check if primary account is changed
    g = Factory.get('Group')(db)
    ou, affiliation, pri = p['ou_id'], p['affiliation'], p['priority']
    k = key(ou, affiliation)
    s = data.get(k)
    if s is None:
        s = data[k] = set()
    for grp in g.list_ou_groups_for(ou, affiliation=affiliation,
                                    member_types=co.virtual_group_ou_accounts,
                                    indirect=False):
        if grp not in data['ignoregroups']:
            s.add(int['group_id'])
    accid = event['subject_entity']
    lst = data['owner']['old']['account']
    logger.debug('before %s', lst)
    for i, item in enumerate(lst):
        if pri < item[1]:
            lst.insert(i, (accid, pri, ou, affiliation))
            break
    else:
        lst.append((accid, pri, ou, affiliation))
    logger.debug('after %s', lst)


def handle_group_add(event, db, co, data):
    """Handle group adding"""
    logger.debug('handle_group_add called')
    # This event will come from this script, as well as OUGroup creation.
    subject, gid = event['subject_entity'], event['dest_entity']
    data['replay'].add((int(subject), int(co.group_add), int(gid)))
    return


def handle_group_rem(event, db, co, data):
    """Handle group membership removing"""
    logger.debug('handle_group_rem called')
    # This event will come from this script, as well as OUGroup deletion.
    subject, gid = event['subject_entity'], event['dest_entity']
    data['replay'].add((int(subject), int(co.group_rem), int(gid)))


def remove_groups(db, entity, groups, co, data):
    """Generate remove events"""
    if entity is None:
        return
    for grp in groups:
        if (entity, int(co.group_rem), grp) not in data['replay']:
            logger.info('Changelogging id:%s group_rem id:%s', entity, grp)
            db.log_change(entity, co.group_rem, grp)


def add_groups(db, entity, groups, co, data):
    """Generate add events"""
    if entity is None:
        return
    for grp in groups:
        if (entity, int(co.group_add), grp) not in data['replay']:
            logger.info('Changelogging id:%s group_add id:%s', entity, grp)
            db.log_change(entity, co.group_add, grp)


def calculate_changes(db, data, co):
    """Calculate the adds and removes for the persons"""
    global logger

    def getoldgroups(obj, tp):
        ret = set()
        map(ret.update, obj['old'][tp].values())
        return ret

    for pid, obj in data['person'].iteritems():
        logger.info('Handling person id:%s', pid)
        oldacc = obj['old']['account'][0][0] if obj['old']['account'] else None
        newacc = obj['new']['account']
        if newacc:
            newacc = newacc[0]
        logger.debug('Oldacc = %s, newacc = %s', oldacc, newacc)
        newgrps = obj['new']['primary']
        oldgrps = getoldgroups(obj, 'primary')
        if newacc != oldacc:
            logger.info('Changing primary for %s', pid)
            remove_groups(db, oldacc, oldgrps, co, data)
            add_groups(db, newacc, newgrps, co, data)
        else:
            logger.info('Updating primary for %s', pid)
            remove_groups(db, oldacc, oldgrps - newgrps, co, data)
            add_groups(db, newacc, newgrps - oldgrps, co, data)
        newgrps = obj['new']['personal']
        oldgrps = getoldgroups(obj, 'personal')
        logger.info('Updating personal for %s', pid)
        remove_groups(db, pid, oldgrps - newgrps, co, data)
        add_groups(db, pid, newgrps - oldgrps, co, data)
    for accid, obj in data['account'].iteritems():
        logger.info('Handling account id:%s', pid)
        oldgrps = set()
        map(oldgrps.update, obj['old'].values())
        newgrps = obj['new']
        remove_groups(db, accid, oldgrps - newgrps, co, data)
        add_groups(db, accid, newgrps - oldgrps, co, data)


def main():
    global logger
    global EVENT_KEY
    logger = Factory.get_logger('cronjob')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-c', '--commit', action='store_true',
                        default=False, help="Commit changes")
    parser.add_argument('-s', '--skip-events', action='store_true',
                        default=False, help="Skip past events (good for initial"
                        "run)")
    args = parser.parse_args()

    db = Factory.get('Database')(client_encoding='UTF-8')
    db.cl_init(change_program="update-ougroups")
    co = Factory.get('Constants')(db)
    clco = Factory.get('CLConstants')(db)
    clh = CLHandler.CLHandler(db)
    data = make_data()

    types = {}

    def make_handler(tp, function, const):
        if tp == 'person':
            filler = fill_person
        elif tp == 'account':
            filler = fill_account
        elif tp == 'both':
            filler = fill_account
            tp = 'person'
        else:
            def handler(event):
                function(event, db, co, data)
            return handler

        def handler(event):
            args = event['change_params']
            if args is not None:
                args = json.loads(args)
            logger.debug('Handler(%s) called for %s', tp, args)
            eid = int(event['subject_entity'])
            datum = data[tp].get(eid)
            try:
                if datum is None:
                    datum = filler(eid, db, co, data)
                function(event, db, co, datum, args)
            except NotFoundError:
                pass
        return handler

    for tp in (('person',
                (clco.person_aff_src_add, handle_person_aff_add),
                (clco.person_aff_src_mod, handle_person_aff_mod),
                (clco.person_aff_src_del, handle_person_aff_del)),
               ('account',
                (clco.account_type_add, handle_account_type_add),
                (clco.account_type_mod, handle_account_type_mod),
                (clco.account_type_del, handle_account_type_del)),
               ('group',
                (clco.group_add, handle_group_add),
                (clco.group_rem, handle_group_rem))):
        t, changes = tp[0], tp[1:]
        for const, adder in changes:
            logger.debug5("Setting up handler %s -> %s", const, adder)
            types[int(const)] = make_handler(t, adder, const)

    events = clh.get_events(EVENT_KEY, types.keys())
    if args.skip_events:
        logger.info('Skipping events')
        for event in events:
            clh.confirm_event(event)
        logger.info('Done')
    else:
        logger.info('Starting event traversing')
        for event in reversed(events):
            logger.debug('Handling event %s', event)
            types.get(int(event['change_type_id']), lambda x: None)(event)
            clh.confirm_event(event)
        logger.info('Done event traversing, calculating changes')
        calculate_changes(db, data, co)
        logger.info('Done')

    if args.commit:
        logger.info('Committing')
        clh.commit_confirmations()
        db.commit()
    else:
        logger.info('Doing rollback')
        db.rollback()

if __name__ == '__main__':
    main()
