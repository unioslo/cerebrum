#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

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

import cerebrum_path
import cereconf

from Cerebrum.modules.no.Indigo.Cweb import State
from Cerebrum.modules.no.Indigo.Cweb import Utils
from Cerebrum.modules.no.Indigo.Cweb import Commands
from Cerebrum.modules.no.Indigo.Cweb import Layout
from Cerebrum.modules.no.Indigo.Cweb.CerebrumGW import CerebrumProxy
from Cerebrum.modules.no.Indigo.Cweb import Errors

import re

class Controller(object):
    def __init__(self, logger, available_actions):
        self.logger = logger
        self.available_actions = available_actions
        
    def process_request(self):
        self.state = State.StateClass(self)
        self.html_util = Utils.HTMLUtil(self.logger, self.state)
        self.cerebrum = CerebrumProxy(self.logger, url=cereconf.CWEB_BOFH_SERVER_URL)
        self.user_cmd = Commands.UserCommands(self.state, self.cerebrum)
        self.group_cmd = Commands.GroupCommands(self.state, self.cerebrum)
        self.person_cmd = Commands.PersonCommands(self.state, self.cerebrum)
        self.misc_cmd = Commands.MiscCommands(self.state, self.cerebrum)
        self.state.read_request_state()
        try:
            self.controller()
        except Errors.CwebException, e:
            self.html_util.error(str(e), self.state)
        except Exception, e:
            er = re.sub(r'.*\:', r'Error:', str(e))
            self.logger.error("Caught unexpected error: ", exc_info=1)
            self.html_util.error("%s" % er)
            
    def login(self):
        uname = self.state.get_form_value('uname')
        session_id = self.cerebrum.login(
            uname, self.state.get_form_value('pass'))
        self.state.set_logged_in(uname, session_id)
        return self.html_util.show_page(Layout.PersonTemplate, 'welcome')

    def logout(self):
        tpl = Layout.SubTemplate(self.state, 'logged_out')
        return tpl.show({}, menu=False)

    def select_target(self):
        t = self.state.form['type'].value
        entity_id = self.state.get_form_value('entity_id')
        if t == 'person':
            self.state.set_target_state('person', entity_id)
            return self.person_cmd.show_person_info(entity_id)
        elif t == 'group':
            name = self.state.get_form_value('name')
            if name is not None:  # Because user info dont return dfg_entity_id
                r = self.cerebrum.group_search('name', name)
                entity_id = r[0]['entity_id']
            self.state.set_target_state('group', entity_id)
            return self.group_cmd.show_group_info(entity_id)
        elif t == 'account': # TODO: Uheldig å bruke user og account om hverandre
            self.state.set_target_state('user', entity_id)
            return self.user_cmd.show_user_info(entity_id)
        else:
            return self.html_util.error("Unknown target type '%s'" % t)

    def controller(self):
        action_map = {
            'do_clear_passwords': [self.user_cmd.clear_passwords],
            'do_group_create': [self.group_cmd.group_create],
            'do_group_find': [self.group_cmd.group_find],
            'do_group_mod': [self.group_cmd.group_mod],
            'do_list_passwords': [self.user_cmd.list_passwords],
            'do_user_password': [self.user_cmd.user_password],
            'do_login': [self.login],
            'do_logout': [self.logout],
            'do_user_create': [self.user_cmd.user_create],
            'do_user_find': [self.user_cmd.user_find],
            'do_person_find': [self.person_cmd.person_find],
            'do_list_new_entities': [self.misc_cmd.list_new_entities],
            'do_select_target': [self.select_target],
            'do_user_priority_mod': [self.user_cmd.user_priority_mod],
            'show_group_create': [self.group_cmd.show_group_create],
            'show_group_info': [self.group_cmd.show_group_info],
            'show_group_mod': [self.group_cmd.show_group_mod],
            'show_group_search': [self.html_util.show_page,
                                  Layout.GroupTemplate, 'group_search'],
            'show_login': [self.html_util.show_page,
                           Layout.SubTemplate, 'login', False],
            'show_person_find': [self.html_util.show_page,
                                 Layout.PersonTemplate, 'person_find'],
            'show_person_info': [self.person_cmd.show_person_info],
            'show_user_create': [self.user_cmd.show_user_create],
            'show_password_letter': [self.user_cmd.show_user_pwd_letter],
            'show_user_get_password': [self.user_cmd.show_user_get_password],
            'show_user_find': [self.html_util.show_page,
                               Layout.UserTemplate, 'user_find'],
            'show_user_password': [self.html_util.show_page,
                                   Layout.UserTemplate, 'user_password']
            }
        action = self.state.get_form_value("action")
        self.logger.debug("Action: %s" % action)
        if not action:
            self.html_util.display(self.html_util.show_page(
                Layout.SubTemplate, 'login', False))
            return
        elif action not in ('do_login', 'do_logout', 'show_login'
                            ) and not self.state.is_logged_in():
            self.html_util.error("Logg inn først")
            return

        # action_map defines all existing commands, but only some of them are
        # available at any given installation.
        # 
        # IVR 2007-03-15 TODO: More elaborate command restriction
        # (i.e. c1-users should not be able to run 'person_find' on
        # anyone). Perhaps in conjunction with cereconf?
        if action not in self.available_actions:
            self.html_util.error("Kommando '%s' er ikke tilgjengelig" % action)
            self.logger.debug("Action '%s' is not available" % action)
            return 
        f = action_map.get(action)
        if not f:
            if (action == 'set_style'):  # TODO: Debug only
                if self.state.get('authlevel') < 'c3':
                    self.html_util.error("Adgang nektet")
                else:
                    style = self.state.get_form_value("val")
                    # self.state.set_style(*style.split(","))
                    self.state.set_style(usertype=style)
                    self.html_util.display(
                        self.html_util.show_page(Layout.PersonTemplate, 'welcome'))
                return
            self.html_util.error("Unknown action: %s" % action)
            self.logger.debug("Unknown action in: %s" % \
                              self.html_util.dump_form(self.state.form))
            return
        self.logger.debug("%s(%s" % (f[0], repr(f[1:])))
        try:
            self.html_util.display(f[0](*f[1:]))
        except Exception, e:
            er = re.sub(r'.*\:', r'Error:', str(e))
            self.logger.error("Caught unexpected error: ", exc_info=1)
            self.html_util.error("%s" % er)

# arch-tag: ce3f527a-7155-11da-985c-65eb434993a3
