#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

import getopt
import sys
import time

import cerebrum_path
import cereconf

from Cerebrum import Constants
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.extlib import logging

def get_constants_by_type(co, class_type):
    ret = []
    for c in dir(co):
        c = getattr(co, c)
        if isinstance(c, class_type):
            ret.append(c)
    return ret

def person_join(old_person, new_person, with_pq):
    old_id = old_person.entity_id
    new_id = new_person.entity_id

    # person_external_id
    types = {}
    for r in old_person.get_external_id():
        types[int(r['id_type'])] = 1
    for r in new_person.get_external_id():
        types[int(r['id_type'])] = 1
    types = types.keys()
    for ss in source_systems:
        logger.debug("person_external_id: %s" % ss)
        old_ids = {}
        new_person.clear()      # Avoid "Attribute '_extid_source' is read-only."
        new_person.find(new_id)
        new_person.affect_external_id(ss, *types)
        old_person.clear()      
        old_person.find(old_id)
        old_person.affect_external_id(ss, *types)
        try:
            for id in old_person.get_external_id(ss):
                new_person.populate_external_id(ss, id['id_type'], id['external_id'])
        except Errors.NotFoundError:
            continue  # Old person didn't have data, no point in continuing
        try:
            for id in new_person.get_external_id(ss):
                new_person.populate_external_id(ss, id['id_type'], id['external_id'])
        except Errors.NotFoundError:
            pass
        old_person.write_db()   # Avoids unique external_id constaint violation
        new_person.write_db()
            
    # person_name
    variants = []
    for c in old_person.list_person_name_codes():
        variants.append(int(c['code']))
    for ss in source_systems:
        logger.debug("person_name: %s" % ss)
        new_person.clear()      
        new_person.find(new_id)
        new_person.affect_names(ss, *variants)
        for c in variants:
            try:
                new_person.populate_name(c, old_person.get_name(ss, c))
            except Errors.NotFoundError:
                pass
            try:
                new_person.populate_name(c, new_person.get_name(ss, c))
            except Errors.NotFoundError:
                pass
        new_person.write_db()
    
    # entity_contact_info
    for ss in source_systems:
        logger.debug("entity_contact_info: %s" % ss)
        new_person.clear()      
        new_person.find(new_id)
        for ci in old_person.get_contact_info(ss):
            new_person.populate_contact_info(
                ci['source_system'], ci['contact_type'], ci['contact_value'],
                ci['contact_pref'], ci['description'])
        for ci in new_person.get_contact_info(ss):
            new_person.populate_contact_info(
                ci['source_system'], ci['contact_type'], ci['contact_value'],
                ci['contact_pref'], ci['description'])
        new_person.write_db()

    # entity_address
    for ss in source_systems:
        logger.debug("entity_address: %s" % ss)
        new_person.clear()      
        new_person.find(new_id)
        try:
            for ea in old_person.get_entity_address(ss):
                new_person.populate_address(
                    ea['source_system'], ea['address_type'],
                    ea['address_text'], ea['p_o_box'], ea['postal_number'],
                    ea['city'], ea['country'])
        except Errors.NotFoundError:
            pass
        try:
            for ea in new_person.get_entity_address(ss):
                new_person.populate_address(
                    ea['source_system'], ea['address_type'],
                    ea['address_text'], ea['p_o_box'], ea['postal_number'],
                    ea['city'], ea['country'])
        except Errors.NotFoundError:
            pass
        new_person.write_db()

    # entity_quarantine
    for q in old_person.get_entity_quarantine():
        logger.debug("entity_quarantine: %s" % q)
        new_person.add_entity_quarantine(
            q['quarantine_type'], q['creator_id'],
            q['description'], q['start_date'], q['end_date'])

    # entity_spread
    for s in old_person.get_spread():
        logger.debug("entity_spread: %s" % s['spread'])
        if not new_person.has_spread(s['spread']):
            new_person.add_spread(s['spread'])

    # person_affiliation
    has_affs = {}
    for ss in source_systems:
        logger.debug("person_affiliation: %s" % ss)
        new_person.clear()      
        new_person.find(new_id)
        do_del = []
        for aff in old_person.list_affiliations(old_person.entity_id, ss, include_deleted=True):
            new_person.populate_affiliation(
                aff['source_system'], aff['ou_id'], aff['affiliation'], aff['status'])
            if aff['deleted_date']:
                do_del.append((int(aff['ou_id']), int(aff['affiliation']),
                               int(aff['source_system'])))
        for aff in new_person.list_affiliations(new_person.entity_id, ss):
            new_person.populate_affiliation(
                aff['source_system'], aff['ou_id'], aff['affiliation'], aff['status'])
            try:
                do_del.remove((int(aff['ou_id']), int(aff['affiliation']),
                               int(aff['source_system'])))
            except ValueError:
                pass
        new_person.write_db()
        for d in do_del:
            new_person.delete_affiliation(*d)
    
    if with_pq:
        join_printerquotas(old_id, new_id)

    # account_type
    account = Factory.get('Account')(db)
    old_account_types = []
    # To avoid FK contraint on account_type, we must first remove all
    # account_types
    for a in account.get_account_types(owner_id=old_person.entity_id):
        account.clear()
        account.find(a['account_id'])
        account.del_account_type(a['ou_id'], a['affiliation'])
        old_account_types.append(a)
        logger.debug("account_type: %s" % account.account_name)
    for r in account.list_accounts_by_owner_id(old_person.entity_id):
        account.clear()
        account.find(r['account_id'])
        account.owner_id = new_person.entity_id
        account.write_db()
        logger.debug("account owner: %s" % account.account_name)
    for a in old_account_types:
        account.clear()
        account.find(a['account_id'])
        account.set_account_type(a['ou_id'], a['affiliation'], a['priority'])
        
    # group_member
    group = Factory.get('Group')(db)
    for g in group.list_groups_with_entity(old_person.entity_id):
        group.clear()
        group.find(g['group_id'])
        logger.debug("group_member: %s" % group.group_name)
        if not group.has_member(new_person.entity_id, g['member_type'], g['operation']):
            group.add_member(new_person.entity_id, g['member_type'], g['operation'])
        group.remove_member(old_person.entity_id, g['operation'])

def join_printerquotas(old_id, new_id):
    # Delayed import in case module is not installed
    from Cerebrum.modules.no.uio.printer_quota import PaidPrinterQuotas
    from Cerebrum.modules.no.uio.printer_quota import PPQUtil

    pq_util = PPQUtil.PPQUtil(db)
    if not pq_util.join_persons(old_id, new_id):
        return  # No changes done, so no more work needed

    ppq = PaidPrinterQuotas.PaidPrinterQuotas(db)
    # Assert that user hasn't received a free quota more than once
    term_init_prefix = PPQUtil.get_term_init_prefix(*time.localtime()[0:3])
    free_this_term = {}
    
    for row in ppq.get_history_payments(
        transaction_type=co.pqtt_quota_fill_free,
        desc_mask=term_init_prefix+'%%',
        person_id=new_id, order_by_job_id=True):
        free_id = row['description'][len(term_init_prefix):]
        if free_this_term.has_key(free_id):
            logger.debug("Undoing pq_job_id %i" % row['job_id'])
            pq_util.undo_transaction(
                new_id, row['job_id'], '',
                'Join-persons resulted in duplicate free quota',
                update_program='join_persons',
                ignore_transaction_type=True)
        free_this_term[free_id] = True

def usage(exitcode=0):
    print """join_persons.py [options] 
  --old entity_id
  --new entity_id
  --pq  also join printerquotas
  --dryrun

Merges all person about person identified by entity_id into the new
person, not overwriting existing values in new person.  The old person
is permanently removed from the database.

"""
    sys.exit(exitcode)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], '',
                                   ['old=', 'new=', 'dryrun',
                                    'pq'])
    except getopt.GetoptError:
        usage(1)

    dryrun = with_pq = False
    old = new = 0
    for opt, val in opts:
        if opt == '--old':
            old = int(val)
        elif opt == '--pq':
            with_pq = True
        elif opt == '--new':
            new = int(val)
        elif opt == '--dryrun':
            dryrun = True
    if not (old and new):
        usage(1)
    old_person = Factory.get('Person')(db)
    old_person.find(old)
    new_person = Factory.get('Person')(db)
    new_person.find(new)
    person_join(old_person, new_person, with_pq)
    old_person.delete()

    if dryrun:
        db.rollback()
    else:
        db.commit()

logger = Factory.get_logger("console")
db = Factory.get('Database')()
db.cl_init(change_program="join_persons")
co = Factory.get('Constants')(db)
source_systems = get_constants_by_type(co, Constants._AuthoritativeSystemCode)

if __name__ == '__main__':
    main()

# arch-tag: 6dc4547c-5906-4db1-958d-a62b1c32a2fc
