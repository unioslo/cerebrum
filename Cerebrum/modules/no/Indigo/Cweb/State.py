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

import cgi
import gdbm  # anydbm is broken in store... segfaults
import os
import time
import Cookie
from random import Random
import time
import md5

import cerebrum_path
import cereconf


class StateClass(object):
    """Handles all state information.

    Client-side state is stored in a cookie with a sessionid. This
    sessionid is used as a key for a dict stored in a gdbm file."""

    # TBD: do we actually want state_keys, or should get_state_dict
    # use a different tecnique to find all relevant keys?  Do we want
    # to limit the legal keys? in add_state?
    state_keys = ('authuser_id', 'authuser_str',
                  'tgt_group_id', 'tgt_group_str',
                  'tgt_person_id', 'tgt_person_str',
                  'tgt_user_id', 'tgt_user_str',
                  'authlevel',

                  'style_location', 'style_usertype',
                  'user_level', 'layout_style'  # Site/bruker spesifike menyer
                  )  
    
    def __init__(self, controller):
        self._db = gdbm.open(cereconf.CWEB_STATE_FILE, 'c')
        self._session_id = None
        self.authuser = None
        self.controller = controller
        self.logger = controller.logger
        self.__logged_in = False
        
    def read_request_state(self):
        if os.environ.get("HTTP_COOKIE", ""):
            cookie = Cookie.SimpleCookie( os.environ.get("HTTP_COOKIE", "") )
            # If the user logged out, we should ignore the cookie even if the
            # browser supplies it.
            if self._session_already_exists(cookie["sessionid"].value):
                self._session_id = cookie['sessionid'].value
                self.authuser = self.get_state_dict()['authuser_str']
                self.__logged_in = True
                self.controller.cerebrum.set_session_id(self._session_id)
                self.logger.debug("Resuming existing session %s for %s",
                                  self._session_id, self.authuser)
                                  
        self.form = cgi.FieldStorage()
        self.controller.html_util.test_cgi(self.form)

    def _make_key(self, session_id, key):
        """Create a key for session_id to index the GDBM file.

        This voodoo is necessary, because the only thing that GDBM works with
        is strings.
        """
        return "%s:%s" % (session_id, key)
    # end _make_key

    def _session_already_exists(self, session_id):
        "Check if session_id exists in the session/connected database."

        for key in self.state_keys:
            if self._db.has_key(self._make_key(session_id, key)):
                return True

        return False
    # end _session_already_exists
        
    def add_state(self, k, v):
        if self._session_id is None:
            self.logger.fatal("oops, add_state called with session_id=None")
            return
        v = str(v)
        self.logger.debug("Add_state(%s, %s)" % (k, v))
        self._db[self._make_key(self._session_id, k)] = v

    def del_state(self, key):
        if self._session_id is None:
            self.logger.fatal("oops, del_state called with session_id=None")
            return

        dbkey = self._make_key(self._session_id, key)
        self.logger.debug("Del_state(%s)", dbkey)
        if self._db.has_key(dbkey):
            del self._db[dbkey]
    # end del_state

    def get(self, key, defval=None):
        key = self._make_key(self._session_id, key)
        if self._db.has_key(key):
            return self._db[key]
        return defval

    def get_state_dict(self):
        """Returns a dict with all stored state.  The dict is
        read-only.  Use add_state to update it."""
        ret = {}
        for k in StateClass.state_keys:
            tmp = self._make_key(self._session_id, k)
            if self._db.has_key(tmp):
                ret[k] = self._db[tmp]
            else:
                ret[k] = None
        return ret
    
    def set_logged_in(self, uname, session_id):
        self._session_id = session_id
        self.controller.cerebrum.set_session_id(session_id)
        userinfo = self.controller.cerebrum.user_info(uname=uname)
        self.cookie = Cookie.SimpleCookie()
        self.authuser = uname
        for k, v in (('authuser_str', uname),
                     ('authuser_id', userinfo['entity_id']),
                     ('owner_id', userinfo['owner_id']),
                     ('owner_type', userinfo['owner_type']),
                     ('sessionid', session_id)):
            # not setting expire -> "on browser close"
            #all_state.cookie[k]['secure'] = 1
            self.add_state(k, v)
        self.cookie['sessionid'] = session_id
        self.add_state('login_time', time.time())

        # set menu-style depending on users permissions
        authlevel = self.controller.cerebrum.get_auth_level()
        if authlevel >= 50:
            authlevel = 'c3'
        elif authlevel > 0:
            authlevel = 'c2'
        else:
            authlevel = 'c1'
        self.add_state('authlevel', authlevel)
        self.set_style(usertype=authlevel)
        self.__logged_in = True

    def is_logged_in(self):
        return self.__logged_in

    def set_logged_out(self):
        if not self.is_logged_in():
            return

        if not self._session_id:
            return

        for key in self.state_keys:
            self.del_state(key)

        self.cookie = ""
        self.authuser = None
        self.__logged_in = False
        self._session_id = None
    # end set_logged_out

    def set_target_state(self, tgt_type, entity_id, name=None):
        self.add_state('tgt_%s_id' % tgt_type, entity_id) # TODO: fetch string
        if name is None:
            if tgt_type == 'person':
                tmp = self.controller.cerebrum.person_info(entity_id)
                name = tmp['name']
            elif tgt_type == 'user':
                tmp = self.controller.cerebrum.user_info(entity_id)
                name = tmp['username']
            elif tgt_type == 'group':
                tmp = self.controller.cerebrum.group_info(entity_id)
                name = tmp['name']
        self.add_state('tgt_%s_str' % tgt_type, name)

    def get_style(self):
        """Style allows different layout depending on what site we're
        viewing as well as the current users permissions.  Returns a
        tuple (location, usertype).  Layout.py use this information to
        fetch the relevant template"""
        # TODO: implement rule for selecting layout based on URL or
        # something so that login can look different for each site
        s = self.get_state_dict()
        return s.get('style_location', 'default'), s.get('style_usertype', None)

    def set_style(self, location=None, usertype=None):
        self.add_state('style_location', location)
        self.add_state('style_usertype', usertype)

    def get_form_value(self, k, v=None):
        if self.form.has_key(k):
            if isinstance(self.form[k], list):
                return [i.value for i in self.form[k]]
            return self.form[k].value
        return v

    def register_login_id(self):
        "Store the temporary login id (check __doc__ in Commands.py) in GDBM."

        # IVR 2007-07-06 FIXME: Code duplication from bofhd.py
        r = Random().random()
        m = md5.new("login-%s-%s" % (time.time(), r))
        login_id = m.hexdigest()
        self._db[login_id] = str(time.time())
        return login_id
    # end register_login_id

    def delete_login_id(self, login_id):
        "The inverse of register_login_id."

        if not self.has_login_id(login_id):
            self.logger.fatal("attempting to delete non-existent login-id %s",
                              login_id)
            return

        del self._db[login_id]
    # end delete_login_id

    def has_login_id(self, login_id):
        return self._db.has_key(login_id)
    # end has_login_id

    def __del__(self):
        self._db.close()

# end StateClass
