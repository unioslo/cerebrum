# -*- coding: iso-8859-1 -*-

# Copyright 2004 University of Oslo, Norway
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

import time

def begin(req, name="", desc=""):
    """Starts a new transaction."""
    if not req.session.has_key('trans_id_counter'):
        req.session['trans_id_counter'] = 1
    new_trans = Transaction(req.session['trans_id_counter'], name, desc)
    if not req.session.has_key('transactions'):
        req.session['transactions'] = []
    req.session['trans_id_counter'] += 1
    req.session['transactions'].append(new_trans)
    req.session['active'] = new_trans
    return new_trans

class Transaction:
    """Temporarly empty transaction untill the metaserver has implementet it!"""
    def __init__(self, id, name="", desc=""):
        self.id = id
        if name:
            self.name = name
        else:
            self.name = "Transaction%i" % self.id
        self.description = desc
        self.objects_num = 0
        self.objects_changed_num = 0
        self.time_started = time.ctime()
        self.last_edited = "0 mins ago"

    def get_id(self):
        return self.id

    def get_name(self):
        return self.name
    
    def set_name(self, name):
        self.name = name

    def get_description(self):
        return self.description

    def set_description(self, description):
        self.description = description

    def get_objects_num(self):
        return self.objects_num

    def get_objects_changed_num(self):
        return self.objects_changed_num

    def get_time_started(self):
        return self.time_started

    def get_last_edited(self):
        return self.last_edited

    def commit(self):
        pass

    def rollback(self):
        pass

# arch-tag: 4133c81a-8bbe-4d6b-b02f-80d858fae8fb
