#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2003-2012 University of Oslo, Norway
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

import pickle
import string

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum import Entity
from Cerebrum.modules import CLHandler
from Cerebrum.modules import NotesUtils


db = Factory.get('Database')()
co = Factory.get('Constants')(db)
clco = Factory.get('Constants')(db)
person = Factory.get('Person')(db)
entityname = Entity.EntityName(db)
ou = Factory.get('OU')(db)
account = Factory.get('Account')(db)
cl = CLHandler.CLHandler(db)
logger = Factory.get_logger("cronjob")


def quick_sync():

    # Change_log entries to react on:
    #
    # OK notes add spread
    # OK notes del spread
    # OK notes changed passwd
    # OK notes add quarantine
    # OK notes del quarantine
    #
    # Secondary:
    # Account changed OU 
    # Account connected same Person changed spread.

    # TODO: force Account-only events
    answer = cl.get_events('notes',
                           (clco.account_password, clco.spread_add,
                            clco.spread_del, clco.quarantine_add,
                            clco.quarantine_del, clco.quarantine_mod,
                            clco.quarantine_refresh))
    event_account = Factory.get("Account")(db)
    entity = Factory.get("Entity")(db)

    for ans in answer:
        chg_type = ans['change_type_id']
        try:
            event_account.clear()
            event_account.find(ans['subject_entity'])
        
            if event_account.has_spread(co.spread_uio_notes_account):
                if chg_type == clco.account_password:
                    change_params = pickle.loads(ans['change_params'])  
                    if change_pw(ans['subject_entity'], change_params):
                        cl.confirm_event(ans)
                elif chg_type == clco.spread_add:
                    change_params = pickle.loads(ans['change_params'])
                    if change_params['spread'] == co.spread_uio_notes_account:
                        if add_user(ans['subject_entity']):
                            cl.confirm_event(ans)
                    else:
                        # unrelated event:
                        cl.confirm_event(ans)
                elif chg_type == clco.spread_del:
                    change_params = pickle.loads(ans['change_params'])
                    if change_params['spread'] == co.spread_uio_notes_account:
                        if delundel_user(ans['subject_entity'], 'splatt'):
                            cl.confirm_event(ans)
                    else:
                        # unrelated event:
                        cl.confirm_event(ans)
                elif (chg_type == clco.quarantine_add or
                      chg_type == clco.quarantine_del or
                      chg_type == clco.quarantine_mod or
                      chg_type == clco.quarantine_refresh):
                    if change_quarantine(ans['subject_entity']):
                        cl.confirm_event(ans)
                else:
                    # unrelated events:
                    cl.confirm_event(ans)
            else:
                # unrelated events:
                cl.confirm_event(ans)
        except Errors.NotFoundError:
            #
            # Accounts are not the only ones that can have the type of events
            # scanned for in the get_events()-call earlier.
            try:
                entity.clear()
                entity.find(ans['subject_entity'])
                # group can have spread_add, e.g. In that case we do not want
                # to see any warnings/errors (it is meaningless).
                logger.debug("Looking for accounts, but found entity id=%s "
                             "(type %s)",
                             ans["subject_entity"], entity.entity_type)
            except Errors.NotFoundError:
                # This is a bit hackish, but we don't want warnings
                # about deleted groups
                # TBD: should we have a coloumn subject_entity_type in
                # change_log so that we can know what type a deleted
                # entity had?
                try:
                    change_params = pickle.loads(ans['change_params'])
                except TypeError, e:
                    # Some events doesn't use change_params, e.g.
                    # quarantine_refresh
                    logger.debug("id:%s: change_params error: %s",
                                 ans['subject_entity'], e)
                else:
                    if (chg_type == clco.spread_del and 
                        change_params['spread'] != co.spread_uio_notes_account):
                            logger.debug("%s is a deleted non-account entity. Ignoring.",
                                         ans['subject_entity'])
                    else:
                        logger.warn("Could not find any *entity* with id=%s "
                                    "although there is a change_log entry for it",
                                    ans['subject_entity'])
            # unrelated events:
            cl.confirm_event(ans)
    cl.commit_confirmations()
# end quick_sync

def change_quarantine(entity_id):
    if NotesUtils.chk_quarantine(entity_id):
        return delundel_user(entity_id, 'splatt')
    else:
        return delundel_user(entity_id, 'unsplatt')

def change_pw(account_id,pw_params):
    pw=pw_params['password']
    user = id_to_name(account_id)
    pw=string.replace(pw,'%','%25')
    pw=string.replace(pw,'&','%26')
    if sock.send('CHPASS&ShortName&%s&pass&%s\n' % (user,pw)):
        sock.read()
    else:
        logger.error('Could not change password for %s!', user)
        return False
    return True

def add_user(account_id):
    # TODO: we are actually using to different ways of accessing
    # information about primary ou for an account in full- and quick
    # sync respectively. This practice should be discontinued in
    # future calender integrations.
    account_name = id_to_name(account_id)        
    pri_ou = NotesUtils.get_primary_ou(account_id)
    if not pri_ou:
        oustr="OU1&%s" % (cereconf.NOTES_DEFAULT_OU)
    else:
        ou = NotesUtils.get_cerebrum_ou_path(pri_ou)
        if ou:
            oustr = ""
            i=0
            ou.reverse()                                
            for elem in ou:
                i = i+1
                oustr="%sOU%s&%s&" % (oustr,i,elem)
        else:
            oustr="OU1&%s" % (cereconf.NOTES_DEFAULT_OU)

    name = get_names(account_id)   
    if name:    
        if sock.send('CREATEUSR&ShortName&%s&FirstName&%s&LastName&%s&%s\n' % (account_name,name[0],name[1],oustr)):
            sock.read()
        else:
            logger.error('Something went wrong, could not create user %s', account_name)
            return False
    if NotesUtils.chk_quarantine(account_id):
        return delundel_user(account_id, 'splatt')      
    return True

def delundel_user(account_id, status):
    account_name = id_to_name(account_id)
    name = get_names(account_id)
    if name:
        cmd = 'DELUNDELUSR&ShortName&%s&FirstName&%s&LastName&%s&Status&%s' % (
            account_name, name[0], name[1], status)
        logger.debug("Sending command: %s" % cmd)
        if sock.send('%s\n' % cmd):
            sock.read()
        else:
            logger.warn('Could not remove user %s!', account_name)
            return False
    return True

def get_names(account_id):
    try:
        account.clear()
        account.find(account_id)
        person_id = account.owner_id
        person.clear()
        person.find(person_id)
    except Errors.NotFoundError:
        logger.warn("find on person or account failed: %s", account_id)
        return False

    try:
        return (person.get_name(co.system_cached, co.name_first),
                person.get_name(co.system_cached, co.name_last))
    except Errors.NotFoundError:
        logger.warn("getting persons name failed, account.owner_id: %s",
                    person_id)
        return False

def id_to_name(id):
    e_type = int(co.entity_account)
    namespace = int(co.account_namespace)
    entityname.clear()
    entityname.find(id)
    name = entityname.get_name(namespace)
    return name

if __name__ == '__main__':
    sock = NotesUtils.SocketCom()  
    quick_sync()
    sock.close()

