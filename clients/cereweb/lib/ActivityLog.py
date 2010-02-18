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

from templates.ActivityLogTemplate import ActivityLogTemplate

class ActivityLog(object):
    def __init__(self):
        if 'al_messages' not in cherrypy.session:
            cherrypy.session['al_messages'] = []
        self.messages = cherrypy.session['al_messages']

    def output(self):
        template = ActivityLogTemplate()
        messages = self.messages[:-6:-1]
        return template.activitylog(messages)

    def __call__(self,*args):
	return self.output()

# arch-tag: ed8a9388-5b3e-4650-96bf-add0ba181744
