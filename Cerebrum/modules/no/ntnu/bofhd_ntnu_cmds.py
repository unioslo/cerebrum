# -*- coding: iso-8859-1 -*-

# Copyright 2002-2004 University of Oslo, Norway
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

# These are extensions to bofh needed by the cereweb web interface

import re
import sys
import time
import os
import cyruslib
import pickle
from mx import DateTime
try:
    from sets import Set
except ImportError:
    # It's the same module taken from python 2.3, it should
    # work fine in 2.2  
    from Cerebrum.extlib.sets import Set    

import cereconf
from Cerebrum import Cache
from Cerebrum import Database
from Cerebrum import Entity
from Cerebrum import Errors
from Cerebrum.Constants import _CerebrumCode, _QuarantineCode, _SpreadCode,\
     _PersonAffiliationCode, _PersonAffStatusCode, _EntityTypeCode
from Cerebrum import Utils
from Cerebrum.modules import Email
from Cerebrum.modules.Email import _EmailSpamLevelCode, _EmailSpamActionCode,\
     _EmailDomainCategoryCode
from Cerebrum.modules import PasswordChecker
from Cerebrum.modules import PosixGroup
from Cerebrum.modules import PosixUser
from Cerebrum.modules import Note
from Cerebrum.modules.bofhd.cmd_param import *
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.modules.bofhd.auth import BofhdAuth, BofhdAuthOpSet, \
     AuthConstants, BofhdAuthOpTarget, BofhdAuthRole
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.uio import PrinterQuotas
from Cerebrum.modules.no.uio import bofhd_uio_help
from Cerebrum.modules.no.uio.access_FS import FS
from Cerebrum.modules.templates.letters import TemplateHandler

class BofhdExtension(object):
    """All CallableFuncs take user as first arg, and are responsible
    for checking necessary permissions"""

    all_commands = {}
    OU_class = Utils.Factory.get('OU')
    external_id_mappings = {}

    def __init__(self, server):
        self.server = server
        self.logger = server.logger
        self.db = server.db
        self.person = Utils.Factory.get('Person')(self.db)
        self.const = self.person.const
        self.name_codes = {}
        for t in self.person.list_person_name_codes():
            self.name_codes[int(t.code)] = t.description
        self.person_affiliation_codes = {}
        self.person_affiliation_statusids = {}
        for c in dir(self.const):
            const = getattr(self.const, c)
            if isinstance(const, _PersonAffStatusCode):
                self.person_affiliation_statusids.setdefault(str(const.affiliation), {})[str(const)] = const
            elif isinstance(const, _PersonAffiliationCode):
                self.person_affiliation_codes[str(const)] = const
        self.external_id_mappings['fnr'] = self.const.externalid_fodselsnr
        # TODO: str2const is not guaranteed to be unique (OK for now, though)
        self.num2const = {}
        self.str2const = {}
        for c in dir(self.const):
            tmp = getattr(self.const, c)
            if isinstance(tmp, _CerebrumCode):
                self.num2const[int(tmp)] = tmp
                self.str2const[str(tmp)] = tmp
        self.ba = BofhdAuth(self.db)
        aos = BofhdAuthOpSet(self.db)
        self.num2op_set_name = {}
        for r in aos.list():
            self.num2op_set_name[int(r['op_set_id'])] = r['name']
        self.change_type2details = {}
        for r in self.db.get_changetypes():
            self.change_type2details[int(r['change_type_id'])] = [
                r['category'], r['type'], r['msg_string']]

        self._cached_client_commands = Cache.Cache(mixins=[Cache.cache_mru,
                                                           Cache.cache_slots],
                                                   size=500)

    def num2str(self, num):
        """Returns the string value of a numerical constant"""
        return str(self.num2const[int(num)])
        
    def str2num(self, string):
        """Returns the numerical value of a string constant"""
        return int(self.str2const[str(string)])

    def get_commands(self, account_id):
        try:
            return self._cached_client_commands[int(account_id)]
        except KeyError:
            pass
        commands = {}
        for k in self.all_commands.keys():
            tmp = self.all_commands[k]
            if tmp is not None:
                if tmp.perm_filter:
                    if not getattr(self.ba, tmp.perm_filter)(account_id, query_run_any=True):
                        continue
                commands[k] = tmp.get_struct(self)
        self._cached_client_commands[int(account_id)] = commands
        return commands

    def get_help_strings(self):
        return (bofhd_uio_help.group_help, bofhd_uio_help.command_help,
                bofhd_uio_help.arg_help)

    def get_format_suggestion(self, cmd):
        return self.all_commands[cmd].get_fs()


    #
    # entity commands
    #
    all_commands['entity_info'] = None
    def entity_info(self, operator, entity_id):
        """Returns basic information on the given entity id"""
        entity = self._get_entity(id=entity_id)
        result = {}
        result['type'] = self.num2str(entity.entity_type)
        result['entity_id'] = entity.entity_id
        if entity.entity_type in \
            (self.const.entity_group, self.const.entity_account): 
            result['creator_id'] = entity.creator_id
            result['create_date'] = entity.create_date
            result['expire_date'] = entity.expire_date
            # FIXME: Should be a list instead of a string, but text clients doesn't 
            # know how to view such a list
            result['spread'] = ", ".join([self.num2str(a.spread)
                                         for a in entity.get_spread()])
        if entity.entity_type == self.const.entity_group:
            result['name'] = entity.group_name
            result['description'] = entity.description
            result['visibility'] = entity.visibility
            try:
                result['gid'] = getattr(entity, 'gid')
            except AttributeError:
                pass    
        elif entity.entity_type == self.const.entity_account:
            result['name'] = entity.account_name
            result['owner_id'] = entity.owner_id
            #result['home'] = entity.home
           # TODO: de-reference disk_id
            #result['disk_id'] = entity.disk_id
           # TODO: de-reference np_type
           # result['np_type'] = entity.np_type
        elif entity.entity_type == self.const.entity_person:   
            result['name'] = entity.get_name(self.const.system_cached,
                                             getattr(self.const,
                                                     cereconf.DEFAULT_GECOS_NAME))
            result['export_id'] = entity.export_id
            result['birthdate'] =  entity.birth_date
            result['description'] = entity.description
            result['gender'] = self.num2str(entity.gender)
            # make boolean
            result['deceased'] = entity.deceased == 'T'
            names = []
            for name in entity.get_all_names():
                source_system = self.num2str(name.source_system)
                name_variant = self.num2str(name.name_variant)
                names.append((source_system, name_variant, name.name))
            result['names'] = names    
            affiliations = []
            for row in entity.get_affiliations():
                affiliation = {}
                affiliation['ou'] = row['ou_id']
                affiliation['affiliation'] = self.num2str(row.affiliation)
                affiliation['status'] = self.num2str(row.status)
                affiliation['source_system'] = self.num2str(row.source_system)
                affiliations.append(affiliation)
            result['affiliations'] = affiliations     
        elif entity.entity_type == self.const.entity_ou:
            for attr in '''name acronym short_name display_name
                           sort_name'''.split():
                result[attr] = getattr(entity, attr)               
                
        return result
    
    # entity history
    all_commands['entity_history'] = None
    def entity_history(self, operator, entity_id, limit=100):
        entity = self._get_entity(id=entity_id)
        self.ba.can_show_history(operator.get_entity_id(), entity)
        result = self.db.get_log_events(any_entity=entity_id)
        events = []
        entities = Set()
        change_types = Set()
        # (dirty way of unwrapping DB-iterator) 
        result = [r for r in result]
        # skip all but the last entries 
        result = result[-limit:]
        for row in result:
            event = {}
            change_type = int(row['change_type_id'])
            change_types.add(change_type)
            event['type'] = change_type

            event['date'] = row['tstamp']
            event['subject'] = row['subject_entity']
            event['dest'] = row['dest_entity']
            params = row['change_params']
            if params:
                params = pickle.loads(params)
            event['params'] = params
            change_by = row['change_by']
            if change_by:
                entities.add(change_by)
                event['change_by'] = change_by
            else:
                event['change_by'] = row['change_program']
            entities.add(event['subject'])
            entities.add(event['dest'])
            events.append(event)
        # Resolve to entity_info, return as dict
        entities = dict([(str(e), self.entity_info(operator,e)) 
                        for e in entities if e])
        # resolv change_types as well, return as dict
        change_types = dict([(str(t), self.change_type2details.get(t))
                        for t in change_types])
        return events, entities, change_types

    #
    # Note commands
    # Notes are simply small messages attached to entities. 
    # 
    # note show
    all_commands['note_show'] = None
    def note_show(self, operator, entity_id):
        entity = Note.EntityNote(self.db)
        entity.find(entity_id)
        #self.ba.can_show_notes(operator.get_entity_id(), entity)
        notes = entity.get_notes()
        result = []
        for note_row in notes:
            note = {}
            # transfer simple values blindly 
            for key in 'note_id creator_id create_date subject description'.split():
                note[key] = note_row[key]
            # translate creator_id into username    
            acc = self._get_account(note_row['creator_id'], idtype='id')
            note['creator'] = acc.account_name
            result.append(note)
        return result    
    
    # note add
    all_commands['note_add'] = None
    def note_add(self, operator, entity_id, subject, description):
        entity = Note.EntityNote(self.db)
        entity.find(entity_id)
        #self.ba.can_add_notes(operator.get_entity_id(), entity)
        entity.add_note(operator.get_entity_id(), subject, description)
        
    # note remove
    all_commands['note_remove'] = None
    def note_remove(self, operator, entity_id, note_id):
        entity = Note.EntityNote(self.db)
        entity.find(entity_id)
        #self.ba.can_remove_notes(operator.get_entity_id(), entity)
        entity.delete_note(operator.get_entity_id(), note_id)

    #
    # group commands
    #

    # group add_entity
    all_commands['group_add_entity'] = None
    def group_add_entity(self, operator, src_entity_id, dest_group_id,
                  group_operator=None):
        """Adds a entity to a group. Both the source entity and the group
           should be entity IDs"""          
        # tell _group_find later on that dest_group is a entity id          
        dest_group = 'id:%s' % dest_group_id
        src_entity = self._get_entity(id=src_entity_id)
        if not src_entity.entity_type in \
            (self.const.entity_account, self.const.entity_group):
            raise CerebrumError, \
              "Entity %s is not a legal type " \
              "to become group member" % src_entity_id
        return self._group_add_entity(operator, src_entity, dest_group,
                               group_operator)

    # group remove_entity
    all_commands['group_remove_entity'] = None
    def group_remove_entity(self, operator, member_entity, group_entity,
                            group_operation):
        group = self._get_entity(id=group_entity)
        member = self._get_entity(id=member_entity)
        return self._group_remove_entity(operator, member, 
                                         group, group_operation)
