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

import Communication
import cereconf
import threading
import time
import traceback

_session_handler = None

class SessionHandler(threading.Thread):
    """The session handler assumes ownership of all sessions provided to it.
    It periodically checks if any of the sessions it maintains has timed out,
    and deletes it if that is the case.
    
    The session timeout value is determined by the constant
    SPINE_SESSION_TIMEOUT in cereconf.  The interval between checking sessions
    is determined by the constant SPINE_SESSION_CHECK_INTERVAL. 
    """
    def __init__(self):
        threading.Thread.__init__(self)
        self._session_lock = threading.RLock()
        self.running = False
        self._sessions = {}
        self._corba_sessions = {}

    def add(self, session):
        com = Communication.get_communication()
        corba_obj = com.servant_to_reference(session)

        self._session_lock.acquire()
        self._corba_sessions[session] = corba_obj
        self._session_lock.release()
        
        self.update(session)
        return corba_obj

    def update(self, session):
        """
        Updates the given sessions timestamp. The handler assumes that it
        controls a session object that has been sent to this method at least
        once. It will delete a session SPINE_SESSION_TIMEOUT seconds after the
        last call to this method with that session as the argument.
        """
        self._session_lock.acquire()
        self._sessions[session] = time.time() + session.get_timeout()
        self._session_lock.release()

    def remove(self, session):
        """Release ownership of the given session."""
        self._session_lock.acquire()
        try:
            self._remove(session)
        except:
            print 'DEBUG: Error while removing session!'
            traceback.print_exc() # TODO: Log instead
        self._session_lock.release()

    def _remove(self, session):
        """This method must ONLY be used internally, and ONLY after acquiring
        the session lock. It removes the given session from the handler."""
        com = Communication.get_communication()
        try:
            com.remove_reference(self._corba_sessions[session])
        except:
            pass
        del self._corba_sessions[session]
        del self._sessions[session]

    def _check_times(self):
        """Internal method called by the thread of control every
        SPINE_SESSION_CHECK_INTERVAL seconds. The method checks for deletable
        sessions, destroys them and removes them from the handler."""
        self._session_lock.acquire()
        now = time.time()
        for session, stamp in self._sessions.items():
            if stamp <= now:
                session.destroy()
                self._remove(session)

        self._session_lock.release()

    def run(self):
        self.running = True
        while self.running:
            self._check_times()
            time.sleep(getattr(cereconf, 'SPINE_SESSION_CHECK_INTERVAL', 10))

    def stop(self):
        self.running = False

def get_handler():
    """Returns the singleton instance of the session handler."""
    global _session_handler
    if _session_handler is None:
        _session_handler = SessionHandler()
    return _session_handler

# arch-tag: 6f392b10-e254-11d9-92c2-10a21545da7f
