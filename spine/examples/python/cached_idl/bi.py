#!/usr/bin/python -i
# -*- encoding: iso-8859-1 -*-

import user
import Spine
import sys
sys.path.append("/home/alfborge/cerebrum/spine/test")
from TestObjects import *

class Wrapper(object):
    def __init__(self):
        print "Loggin in..."
        self.username = Spine.conf.get('login', 'username')
        self.password = Spine.conf.get('login', 'password')
        self.spine = Spine.connect()
        self.session = self.spine.login(self.username, self.password)
        self.tr = self.session.new_transaction()
        self.cmds = self.tr.get_commands()
    
    def __del__(self):
        print "Logging out..."
        self.tr.rollback()
        self.session.logout()

w = Wrapper()
tr, cmds = w.tr, w.cmds
groups, accounts = tr.get_group_searcher().dump(), tr.get_account_searcher().dump()

def pga():
    p = DummyPerson(w.session)
    a = DummyAccount(w.session, p)
    g = DummyGroup(w.session)
    g.add_member(a)
    return p,g,a

