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
from Cerebrum.modules.no.uio import bofhd_uio_cmds
from Cerebrum.modules.no.uio.access_FS import FS
from Cerebrum.modules.templates.letters import TemplateHandler

class BofhdExtension(bofhd_uio_cmds.BofhdExtension):
    """Just extend UiOs excellent BofhdExtension"""
    #
    # Note commands
    # Notes are simply small messages attached to entities. 
    # 

    # This is not nice-looking ..
    all_commands = bofhd_uio_cmds.BofhdExtension.all_commands.copy()
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
    
    all_commands['operator_history'] = None
    def operator_history(self, operator, start_id=0):
        events = self.db.get_log_events(start_id=start_id, 
                               change_by=operator.get_entity_id())
        return self._unwrap_events(operator, events)
    
    # entity history
    all_commands['entity_history'] = None
    def entity_history(self, operator, entity_id, limit=100):
        entity = self._get_entity(id=entity_id)
        self.ba.can_show_history(operator.get_entity_id(), entity)
        result = self.db.get_log_events(any_entity=entity_id)
        # (dirty way of unwrapping DB-iterator) 
        result = [r for r in result]
        # skip all but the last entries 
        result = result[-limit:]
        return self._unwrap_events(operator, result)
    
    def _unwrap_events(self, operator, result):    
        """Resolve stuff in event objects, suitable for
           passing back by commands like entity_history 
           and operator_history"""
        events = []
        entities = Set()
        change_types = Set()
        for row in result:
            event = {}
            change_type = int(row['change_type_id'])
            change_types.add(change_type)
            event['type'] = change_type
            event['id'] = int(row.change_id)

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

# arch-tag: 9bdf84de-c837-4e5b-8c69-840e8ee2c5e0
