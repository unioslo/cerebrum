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
import forgetHTML as html
from Cerebrum.web.templates.TransactionsTemplate import TransactionsTemplate

def begin():
    """Starts a new transaction."""
    return Transaction(20)

#subclass Division to be included in a division..
class TransactionBox(html.Division):
    """Creates the box for transactions on the left corner."""
    def __init__(self):
        self.active = Transaction(5)
        self.transactions = [Transaction(1),
                             Transaction(2, "TransTycoon"),
                             Transaction(2000)]
    
    def output(self):
        template = TransactionsTemplate()
        return template.transactionbox(self.transactions, self.active)

class Transaction:
    """Temporarly empty transaction untill the metaserver has implementet it!"""
    def __init__(self, id, name=""):
        self.id = id
        if name:
            self.name = name
        else:
            self.name = "Transaction%i" % self.id
        self.objects_num = 10
        self.objects_changed_num = 7
        self.time_started = time.ctime()
        self.last_edited = "3 mins ago"

    def get_id(self):
        return self.id

    def get_name(self):
        return self.name

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
