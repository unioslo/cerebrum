# -*- coding: iso-8859-1 -*-

from Cerebrum.modules.no.Indigo.Cweb.Layout import UserTemplate, GroupTemplate, PersonTemplate, SubTemplate
from Cerebrum.modules.no.Indigo.Cweb import Errors

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

    def user_find(self):
        r = self.cerebrum.user_find(
            self.state.get_form_value('search_type'),
            self.state.get_form_value('search_value'))
        if len(r) == 1:
            self.state.set_target_state('user', r[0]['entity_id'])
            return self.show_user_info(r[0]['entity_id'])
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

    def list_passwords(self):
        tpl = UserTemplate(self.state, 'list_passwords')
        p = self.cerebrum.list_passwords()
        return tpl.show({'pwdlist': p})

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
            group = selg.cerebrum.group_info(entity_id=owner_id)
            ret['group_name'] = group['name']
        return tpl.show(ret)

class GroupCommands(VirtualCommands):
    def __init__(self, state, cerebrum):
        self.state = state
        self.cerebrum = cerebrum

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
        spreads = self.state.get_form_value('spreads', [])
        self.cerebrum.spread_add('group', name, spreads)
        return self.show_group_info(name=name)
    
    def group_mod(self):
        tgt_id = self.state.get_form_value('target_id')
        if self.state.get_form_value('choice') == 'Fjern':
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
        person_spreads = self.cerebrum.get_entity_spreads(entity_id)
        userlist = self.cerebrum.user_find('owner', entity_id)
        for u in userlist:
            u['spreads'] = self.cerebrum.get_entity_spreads(u['entity_id'])
            try:
                u['email'] = self.cerebrum.get_default_email(u['entity_id'])
            except:
                u['email'] = 'unknown'
            u['groups'] = self.cerebrum.group_user(entity_id=u['entity_id'])
        return tpl.show({'person': self.cerebrum.convert(person),
                         'userlist': userlist,
                         'person_spreads': person_spreads})

    def person_find(self):
        r = self.cerebrum.person_find(
            self.state.get_form_value('search_type'),
            self.state.get_form_value('search_value'))
        for t in r:
            t['entity_id'] = t['id']
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
