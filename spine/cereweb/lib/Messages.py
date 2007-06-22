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

import mx.DateTime
import cherrypy

class Message(object):
    def __init__(self, title, message, is_error=False, date=None, link=None, tracebk=None):
        self.__msg = {
            'title': title,
            'message': message,
            'is_error': is_error,
            'tracebk': tracebk,
            'link': link,
            'date': date or mx.DateTime.now(),
        }

    def to_activitylog(self):
        link = self.__msg.get('link', '')
        if link:
            link = "%s :" % link
        error = self.__msg.get('is_error', '')
        error = error and "(error)" or ''

        return """
        <div class="amsg">
            %(link)s
            %(msg)s
            %(error)s
        </div>""" % {
            'link': link,
            'msg': self.__msg.get('message'),
            'error': error,
        }

    def __getattr__(self, attr):
        if attr == '__msg':
            return self.__msg
        elif attr == '__dict__':
            return self.__dict__

        if attr in self.__msg:
            return self.__msg.get(attr) 
        else:
            return self.__dict__[attr]

    def __str__(self):
        error = self.__msg.get('is_error')
        error = error and ' class="error"' or ''
        traceback = self.__msg.get('tracebk')
        if traceback:
            traceback = """
            <div class="traceback">
                <pre>%s</pre>
            </div>""" % traceback
        else:
            traceback = ''

        data = {
            'error': error,
            'traceback': traceback,
        }
        data.update(self.__msg)

        return """
        <div%(error)s>
            <h3>%(title)s</h3>
            <div class="short">
                %(message)s
            </div>
            %(traceback)s
        </div>""" % data 

def queue_message(*args, **kwargs):
    """Queue a message.
    
    The message will be displayed next time a Main-page is showed.
    If error is true, the message will be indicated as such.
    Link is used in activitylog so the user knows which
    object the action was on, should be a string linking to
    the object.
    """

    msg = Message(*args, **kwargs)
    for i in ['messages', 'al_messages']:
        try:
            cherrypy.session.get(i).append(msg)
        except AttributeError, e:
            cherrypy.session[i] = [msg]

def get_messages():
    msgs = cherrypy.session.get('messages', [])
    cherrypy.session['messages'] = []
    return msgs
