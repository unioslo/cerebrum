#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2005, 2006, 2007 University of Oslo, Norway
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

from Cerebrum.modules.no.Indigo.Cweb.Layout import UserTemplate, GroupTemplate, PersonTemplate, SubTemplate
from Cerebrum.modules.no.Indigo.Cweb import Errors
from Cerebrum.extlib.sets import Set as set

class VirtualCommands(object):  # TODO: Not a good name...; the class is virtual
    def _get_target_id(self, entity_id=None, tgt_type=None):
        if not entity_id:
            entity_id = self.state.get_form_value('entity_id')
            if not entity_id and tgt_type == 'person':
                entity_id = self.state.get('owner_id')
        if not entity_id or entity_id == "None":
            raise Errors.MustSelectTarget(
                "Please use find to select a target first")
        return entity_id

class UserCommands(VirtualCommands):
    def __init__(self, state, cerebrum):
        self.state = state
        self.cerebrum = cerebrum
        self.logger = state.logger

    def clear_passwords(self):
        self.cerebrum.clear_passwords()
        return self.list_passwords()

    def user_create(self):
        #self.state.controller.html_util.display(
        #    self.state.controller.html_util.dump_form(self.state.form))
        self.cerebrum.user_create(self.state.get_form_value('name'),
                                  self.state.get_form_value('owner_id'))
        tpl = UserTemplate(self.state, 'user_create_ok')
        return tpl.show({})

    def run_person_command(self, command_name, person_id):
        """Just pass the call to the PersonCommands instance."""

        return getattr(self.state.controller.person_cmd, command_name)(person_id)
    # end show_person_info

    def user_find(self):
        r = self.cerebrum.user_find(
            self.state.get_form_value('search_type'),
            self.state.get_form_value('search_value'))
        if len(r) == 1:
            # showing user info is much like showing person info
            self.state.set_target_state('person', r[0]['owner_id'])
            return self.run_person_command("show_person_info", r[0]['owner_id'])
        tpl = UserTemplate(self.state, 'user_find_res')
        return tpl.show({'userlist': r})

    def user_password(self):
        if self.state.get_form_value('entity_id'):
            entity_id = self.state.get_form_value('entity_id')
        else:
            if self.state.get_form_value('newpass') != self.state.get_form_value('newpass2'):
                self.state.controller.html_util.error("Passordene er ulike")
                return
            entity_id = self.state.get('authuser_id')
        self.cerebrum.user_password(
            entity_id, self.state.get_form_value('newpass'))
        tpl = UserTemplate(self.state, 'user_password_ok')
        return tpl.show({})

    def user_priority_mod(self):
        """Shuffle accounts according to priorities."""

        from_priority = int(self.state.get_form_value('from_priority'))
        victim = self.state.get_form_value('owner_id')

        user_priorities = self.run_person_command("list_user_priorities",
                                                  victim)
        user_to_change = [x for x in user_priorities
                          if int(x['priority']) == from_priority]
        if user_to_change:
            user_to_change = user_to_change[0]['uname']
            
        primary_user = None
        to_priority = None
        if user_priorities:
            primary_user = user_priorities[0]['uname']
            to_priority = user_priorities[0]['priority']

        # Either we have no priorities at all, or the one we are changing from
        # is completely bogus. Either way, it's an error.
        if not user_to_change or not primary_user:
            self.state.controller.html_util.error("Ingen slik prioritet finnes: %s" %
                                                  from_priority)

        # Now, we swap the priorities. Actually, we just push user_to_change
        # into the topmost slot. This keeps the relative order of all the
        # other priorities for the person. 
        self.cerebrum.person_set_user_priority(user_to_change,
                                               from_priority, to_priority)

        # If everything is ok, then we just re-display the page.
        self.state.set_target_state('person', victim)
        return self.run_person_command("show_person_info", victim)
    # end user_priority_mod

  # TODO: this functionality will be removed when we introduce event-based
  #       export system updates
    def show_user_get_password(self):
        tpl = UserTemplate(self.state, 'old_passwords')
        id = self.state.get_form_value('entity_id')
        ret = self.cerebrum.user_get_pwd(id)
        return tpl.show(ret)
    
    def list_passwords(self):
        tpl = UserTemplate(self.state, 'list_passwords')
        p = self.cerebrum.list_passwords()
        return tpl.show({'pwdlist': p})

    def show_user_pwd_letter(self):
        tpl = UserTemplate(self.state, 'password_letter')
        uname = self.state.get_form_value('username')
        uinfo = self.cerebrum.user_info(uname=uname)
        pwd = self.state.get_form_value('pwd')
        email = self.cerebrum.get_default_email(uinfo['entity_id'])
        ret = {'uname': uname,
               'pwd': pwd,
               'email': email}
        return tpl.show(ret)

    def show_user_create(self):
        tpl = UserTemplate(self.state, 'user_create')
        owner_id = self.state.get_form_value('owner_id')
        owner_type = self.state.get_form_value('owner_type')
        ret = {'owner_id': owner_id,
               'owner_type': owner_type,
               'uname': '',
               'more_unames': ''}
        if owner_type == 'person':
            person = self.cerebrum.person_info(entity_id=owner_id)
            uname = self.cerebrum.user_suggest_uname(owner_id)
            if uname:
                ret['uname'] = uname[0]
                ret['more_unames'] = ', '.join(uname[1:5])
            ret['person_name'] = person['name']
        else:
            group = self.cerebrum.group_info(entity_id=owner_id)
            ret['group_name'] = group['name']
        return tpl.show(ret)

class GroupCommands(VirtualCommands):
    def __init__(self, state, cerebrum):
        self.state = state
        self.cerebrum = cerebrum
        self.logger = state.logger

    def show_group_create(self):
        tpl = GroupTemplate(self.state, 'group_create')
        return tpl.show({
            'spreads': [s for s in  self.cerebrum.list_defined_spreads()
                        if s['entity_type'] == 'group']})

    def show_group_mod(self, entity_id=None):
        tpl = GroupTemplate(self.state, 'group_mod')
        if not entity_id:
            entity_id=self._get_target_id()
        r = self.cerebrum.group_list(entity_id=entity_id)
        return tpl.show({'members': r,
                         'target_id': entity_id})

    def group_create(self):
        name = self.state.get_form_value('name')
        self.cerebrum.group_create(name,
                                   self.state.get_form_value('description'))

        # IVR 2007-03-12 It could be that the spreads listed in
        # cereconf.BOFHD_NEW_GROUP_SPREADS and the ones supplied in cweb are
        # partially overlapping. In such a case, it is more user-friendly to
        # guard against 'duplicate insert' error.
        new_spreads = self.state.get_form_value('spreads', [])
        group_object = self.cerebrum.group_info(name=name)
        existing_spreads = [x['spread'] for x in
                    self.cerebrum.get_entity_spreads(group_object["entity_id"])]
        spreads_to_add = [s for s in new_spreads if s not in existing_spreads]
        self.cerebrum.spread_add('group', name, spreads_to_add)
        return self.show_group_info(name=name)
    
    def group_mod(self):
        tgt_id = self.state.get_form_value('target_id')
        if self.state.get_form_value('choice') == 'Meld ut':
            ids = self.state.get_form_value('remove_member', [])
            if ids:
                self.cerebrum.group_remove_entity(ids, tgt_id)
        else:
            ids = []
            for i in self.state.get_form_value('new_users').split():
                i = i.strip()
                if i:
                    tmp = self.cerebrum.user_info(uname=i)
                    ids.append(tmp['entity_id'])
            self.cerebrum.group_add_entity(ids, tgt_id)
        return self.show_group_mod(tgt_id)

    def show_group_info(self, entity_id=None, name=None):
        tpl = GroupTemplate(self.state, 'group_info')
        if name:
            r = self.cerebrum.group_info(name=name)
        else:
            r = self.cerebrum.group_info(entity_id=entity_id)
        return tpl.show({
            'group': r,
            'spreads': self.cerebrum.get_entity_spreads(r['entity_id'])})
    
    def group_find(self):
        r = self.cerebrum.group_search(
            self.state.get_form_value('search_type'),
            self.state.get_form_value('search_value'))
        if len(r) == 1:
            self.state.set_target_state('group', r[0]['entity_id'])
            return self.show_group_info(r[0]['entity_id'])
        tpl = GroupTemplate(self.state, 'group_search_res')
        return tpl.show({'grouplist': r})

class PersonCommands(VirtualCommands):
    def __init__(self, state, cerebrum):
        self.state = state
        self.cerebrum = cerebrum
        self.logger = state.logger

    def show_person_info(self, entity_id = None):
        tpl = PersonTemplate(self.state, 'person_info')
        entity_id = self._get_target_id(entity_id,
                                        tgt_type='person')
        person = self.cerebrum.person_info(entity_id=entity_id)
        if not person:
            self.state.controller.html_util.error("no person")
        # TODO: only the first of the fnrs found is now shown
        #       this should be fixed by parsing fnrs in cerebrum.person_info     
        for k, v in person.iteritems():
            if k == 'fnrs':
                person['fnrs'] = v[0]['fnr'] + " (Fra: " + v[0]['fnr_src'] + ")"
        # ENDTODO
        person_spreads = self.cerebrum.get_entity_spreads(entity_id)
        userlist = self.cerebrum.user_find('owner', entity_id)
        for u in userlist:
            u['spreads'] = self.cerebrum.get_entity_spreads(u['entity_id'])
            try:
                u['email'] = self.cerebrum.get_default_email(u['entity_id'])
            except:
                u['email'] = 'unknown'
            u['groups'] = self.cerebrum.group_user(entity_id=u['entity_id'])

        affiliations = list()
        for data in person.get("affiliations", []):
            # The format uglyness is to avoid situations when the value of key
            # 'aff_sted_desc' is None.
            affiliations.append("%s %s(fra %s)" % (data["aff_status"],
                                                   (data["aff_sted_desc"] or "") + " ",
                                                   data["source_system"]))

        user_priorities = self.list_user_priorities(entity_id)
        return tpl.show({'person': self.cerebrum.convert(person),
                         'userlist': userlist,
                         'person_spreads': person_spreads,
                         'affiliations': affiliations,
                         'user_priorities': user_priorities,})

    def list_user_priorities(self, person_id):
        """Return a list of all accounts and their priorities."""
        user_priorities = self.cerebrum.person_list_user_priorities(
                              entity_id=person_id)
        # sort them by priorities before returning
        user_priorities.sort(lambda x, y: cmp(x["priority"],
                                              y["priority"]))
        return user_priorities
    # end list_user_priorities

    def person_find(self):
        s_type = s_val = None
        if self.state.get_form_value('search_type') == 'schoolname':
            s_type = 'ou'
            self.logger.debug(s_type)
            s_val = self.cerebrum.find_school(self.state.get_form_value('search_value'))
            r = self.cerebrum.person_find(s_type, s_val)
        else:
            r = self.cerebrum.person_find(
                self.state.get_form_value('search_type'),
                self.state.get_form_value('search_value'))

        ac_list = set(self.cerebrum.list_active())
        for t in r:
            t['entity_id'] = t['id']
        r = [ t for t in r if t['entity_id'] in ac_list ]
        if len(r) == 1:
            self.state.set_target_state('person', r[0]['entity_id'])
            return self.show_person_info(r[0]['entity_id'])
        tpl = PersonTemplate(self.state, 'person_find_res')
        return tpl.show({'personlist': r})

class MiscCommands(VirtualCommands):
    def __init__(self, state, cerebrum):
        self.state = state
        self.cerebrum = cerebrum
        self.logger = state.logger

    def list_new_entities(self):
        days = self.state.get_form_value('dager')
        changes = []
        if days:
            changes = self.cerebrum.misc_history(days)
        tpl = PersonTemplate(self.state, 'list_new_entities')
        return tpl.show({'changes': changes,
                         'days': days})

# arch-tag: cdd634ac-7155-11da-8a75-c6a0738f99aa
