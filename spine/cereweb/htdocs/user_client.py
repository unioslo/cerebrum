# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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

import cherrypy

from lib import utils
from gettext import gettext as _
from lib.Main import Main
from lib.utils import commit, commit_url, queue_message, object_link
from lib.utils import transaction_decorator, redirect, redirect_object
from lib.templates.InsightTemplate import InsightTemplate

def index(transaction):
    page = InsightTemplate()
    username = cherrypy.session.get('username', '')
    account = transaction.get_commands().get_account_by_name(username)
    page.tr = transaction
    page.account = account
    res = str(page)
    return [res]
index = transaction_decorator(index)
index.exposed = True

def set_password(transaction, **vargs):
	myId = vargs.get('id')
	pass1 = vargs.get('passwd1')
	pass2 = vargs.get('passwd2')
	if myId and pass1 and pass2 and pass1 == pass2:
	  account = transaction.get_account(int(myId))
	  account.set_password(pass1)
	  transaction.commit()
	elif (not myId):
		print 'not myId'
	elif (not pass1):
		print 'not pass1'
	elif ( not pass2):
		print 'not pass2'
	elif ( not pass1 == pass2 ):
		print 'pass1 != pass2'

	utils.redirect('/user_client')
set_password = transaction_decorator(set_password)
set_password.exposed = True

