#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2015-2018 University of Oslo, Norway
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
""" Session handling for bofhd.


Configuration
-------------

This module actively uses the cereconf variables:

BOFHD_SHORT_TIMEOUT
   Certain hosts can have a shorter session timeout than others. The timeout
   for these hosts are given in this cereconf variable. Timeout is given in
   seconds.

BOFHD_SHORT_TIMEOUT_HOSTS
   Specifies the hosts that should have a shorter timeout value. This value
   shoudl be an iterable of strings. Each string is a subnet (CIDR-notation) or
   a single IP-address.


History
-------

This class used to be a part of the bofhd server script itself. It was
moved to a separate module after:

    commit 57e594433f24efbbe5175e4b4800092c0603edcf
    Merge: 70ca8e7 6c71d5e
    Date:   Fri Jan 30 12:20:40 2015 +0100

"""

import json
import re
import struct
import socket
import types
import time
import hashlib
import random
import os

import cereconf

from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError
from Cerebrum.modules.bofhd import errors


# This regex is too permissive for IP-addresses, but that does not matter,
# since we use a library function that traps non-sensical values.
_subnet_rex = re.compile(r"((\d+)\.(\d+)\.(\d+)\.(\d+))\/(\d+)")


def ip_to_long(ip_address):
    """Convert IP address in string notation to a 4 byte long.

    @type ip_address: basestring
    @param ip_address:
      IP address to convert in A.B.C.D notation

    """
    return struct.unpack("!L", socket.inet_aton(ip_address))[0]


def ip_subnet_slash_to_range(subnet):
    """Convert a subnet '/'-notation to a (start, stop) pair.

    IVR 2008-09-01 FIXME: Duplication of IPUtils.py. This code should be in
    its own module dealing with IP addresses.

    @type subnet: basestring
    @param subnet:
      Subnet in '/' string format (i.e. A.B.C.D/X, where 0 <= A, B, C, D <=
      255, 1 < X <= 32).

    @rtype: tuple (of 32 bit longs)
    @return:
      A tuple (start, stop) with the lowest and highest IP address on the
      specified subnet.

    """
    def netmask_to_intrep(netmask):
        return pow(2L, 32) - pow(2L, 32-int(netmask))

    match = _subnet_rex.search(subnet)
    if not match:
        raise ValueError("subnet <%s> is not in valid '/'-notation" % subnet)

    subnet = match.group(1)
    netmask = int(match.group(6))
    if not (1 <= netmask <= 31):
        raise ValueError("netmask %d in subnet <%s> is invalid" %
                         (netmask, subnet))

    tmp = ip_to_long(subnet)
    start = tmp & netmask_to_intrep(netmask)
    stop = tmp | (pow(2L, 32) - 1 - netmask_to_intrep(netmask))
    return start, stop


def _get_short_timeout():
    """ Get the shorter timeout for the short timeout hosts.

    This method fetches and validates the BOFHD_SHORT_TIMEOUT cereconf
    setting. The shorter timeout is used for hosts fetched by
    L{_get_short_timeout_hosts}.

    """
    if hasattr(cereconf, "BOFHD_SHORT_TIMEOUT"):
        timeout = int(cereconf.BOFHD_SHORT_TIMEOUT)
        if not (60 <= timeout <= 3600*24):
            raise ValueError(
                u'Bogus BOFHD_SHORT_TIMEOUT timeout: {:d}s'.format(
                    cereconf.BOFHD_SHORT_TIMEOUT))
        return timeout
    return None


def _get_short_timeout_hosts():
    """ Build a list of hosts, where shorter session expiry is in place.

    This static method populates with _short_timeout_hosts with a list of
    IP address pairs. Each pair represents an IP range. All bofhd *clients*
    connecting from addresses within this range will be timed out much
    faster than the standard L{_auth_timeout}. The specific timeout value
    is assigned here as well.

    This method has been made static for performance reasons.

    Caveat: It is probably a very bad idea to put a lot of IP addresses
    into BOFHD_SHORT_TIMEOUT_HOSTS. L{_short_timeout_hosts} is traversed
    to generate SQL once for every command received by bofhd.

    """
    # Contains a list of pairs (first address, last address). Note that a
    # single IP X will be mapped to a pair (X, X) (a single IP is a range
    # with 1 element). Ranges are *inclusive* (as opposed to python's
    # range())
    hosts = list()
    if hasattr(cereconf, "BOFHD_SHORT_TIMEOUT_HOSTS"):
        for ip in cereconf.BOFHD_SHORT_TIMEOUT_HOSTS:
            # It's a subnet (A.B.C.D/N)
            if '/' in ip:
                low, high = ip_subnet_slash_to_range(ip)
                hosts.append((ip, low, high))
            # It's a simple IP-address
            else:
                addr_long = ip_to_long(ip)
                hosts.append((ip, addr_long, addr_long))
    return hosts


class BofhdSession(object):

    """ Handle database sessions for the BofhdServer.

    This object is used to store and retrieve sessions from the database, which
    in turn is used to validate session_ids from clients.

    A session_id is valid if it (a) exists in the database, and (b) is not
    timed out. A session can time out in two ways:

    * If a certain time passes from the last time the client authenticated with
      a username and password, the session is invalidated.

      The authentication timeout is controlled by the _auth_timeout attribute.

    * The session tracks the last time an action was performed. If a certain
      time passes from the last action (the client is idle), the session is
      also invalidated.

      The idle timeout is controlled by attributes _seen_timeout and
      _short_timeout. The _short_timeout attribute applies to hosts in the
      _short_timeout_hosts attribute, and is intended for web clients and other
      clients that should not keep an idle session for too long.

    """

    _auth_timeout = 3600*24*7
    """ In seconds, how long a session should live after authentication. """

    _seen_timeout = 3600*24
    """ In seconds, how long a session should 'idle'. """

    _short_timeout = _get_short_timeout()
    """ In seconds, how long a session should 'idle' for certain clients. """

    _short_timeout_hosts = _get_short_timeout_hosts()
    """ Which clients should have the shorter timeout setting. """

    def __init__(self, database, logger, session_id=None, remote_address=None):
        """ Create a new session.

        :param Database database: A database connection.
        :param str session_id: The session_id for this session.
        :param str remote_address: The IP of the client for this session.

        """
        self._db = database
        self.logger = logger
        if not isinstance(session_id, (types.NoneType, str, unicode)):
            raise errors.CerebrumError(
                "Wrong session id type: %s, expected str or None" %
                type(session_id))
        self._id = str(session_id)
        self._entity_id = None
        self._owner_id = None
        self.remote_address = remote_address

    @classmethod
    def _log_short_timeouts(cls, logger):
        u""" Log the short timeout settings.

        Logs the settings to the specified logger with level 'DEBUG'.
        """
        if cls._short_timeout is not None:
            logger.debug("Short-lived sessions expire after %ds",
                         cls._short_timeout)
        if cls._short_timeout_hosts:
            for ip, low, high in cls._short_timeout_hosts:
                logger.debug("Sessions from IP %s [%s, %s] will be "
                             "short-lived", ip, low, high)

    def _get_timeout_timestamp(self, key):
        """ Get the current timeout threshold for this session.

        :param str key: Which threshold to get (auth, seen or short).

        :return:
            Returns the threshold timestamp for when this session is
            invalidated, according to the _<key>_timeout class attribute.

        """
        try:
            seconds = getattr(self, '_%s_timeout' % key)
        except AttributeError:
            raise RuntimeError("Invalid timeout setting '%s'" % key)
        ticks = int(time.time() - seconds)
        return self._db.TimestampFromTicks(ticks)

    def _remove_old_sessions(self):
        """ Remove timed out sessions.

        We remove any authenticated session-ids that was authenticated more
        than _auth_timeout seconds ago, or hasn't been used in the last
        _seen_timeout seconds.
        """
        thresholds = dict(((key, self._get_timeout_timestamp(key)) for key in
                           ('auth', 'seen')))

        # Clear any session_state data tied to the sessions
        self._db.execute("""
        DELETE FROM [:table schema=cerebrum name=bofhd_session_state]
        WHERE exists (SELECT 'foo'
                      FROM[:table schema=cerebrum name=bofhd_session]
                      WHERE bofhd_session.session_id =
                            bofhd_session_state.session_id
                      AND (bofhd_session.auth_time < :auth
                           OR bofhd_session.last_seen < :seen))""",
                         thresholds)

        # Clear the actual sessions.
        self._db.execute("""
        DELETE FROM [:table schema=cerebrum name=bofhd_session]
        WHERE auth_time < :auth OR last_seen < :seen""",
                         thresholds)

        # Clear sessions for _short_timeout_hosts.
        self.remove_short_timeout_sessions()

    def remove_short_timeout_sessions(self):
        """ Remove bofhd sessions with a shorter timeout value.

        For some clients, it is desireable to remove sessions much faster than
        the standard _auth_timeout value.

        """
        if not self._short_timeout_hosts:
            return
        sql = []
        params = {}
        # 'index' is needed to number free variables in the SQL query.
        for index, (ip, ip_start, ip_stop) in enumerate(
                self._short_timeout_hosts):
            sql.append("(:start%d <= bs.ip_address AND "
                       " bs.ip_address <= :stop%d)" % (index, index))
            params["start%d" % index] = ip_start
            params["stop%d" % index] = ip_stop

        # first nuke all the associated session states
        stmt = """
        DELETE FROM [:table schema=cerebrum name=bofhd_session_state] bss
        WHERE EXISTS (SELECT 1
                      FROM [:table schema=cerebrum name=bofhd_session] bs
                      WHERE bss.session_id = bs.session_id
                      AND (%s)
                      AND bs.last_seen < :last_seen
                      )
        """ % ' OR '.join(sql)
        params["last_seen"] = self._get_timeout_timestamp('short')

        self._db.execute(stmt, params)

        # then nuke all the sessions
        stmt = """
        DELETE FROM [:table schema=cerebrum name=bofhd_session] bs
        WHERE bs.last_seen < :last_seen AND (%s)
        """ % ' AND '.join(sql)
        self._db.execute(stmt, params)

    # TODO: we should remove all state information older than N
    # seconds
    def set_authenticated_entity(self, entity_id, ip_address):
        """Create persistent entity/session mapping; return new session_id.

        This method assumes that entity_id is already sufficiently
        authenticated, so the actual authentication of entity_id
        authentication must be done before calling this method.

        @param entity_id:
          Account id for the account associated with this session. The
          privileges of this account will be used throughout the session.

        @type ip_address: basestring
        @param ip_address:
          IP address of the client that made the connection in A.B.C.D
          notation

        """
        try:
            # /dev/random doesn't provide enough bytes
            r = os.urandom(48)
            # If a randomness source is not found,
            # NotImplementedError will be raised.
            # This should be handled by the caller.
        except IOError:
            r = random.Random().random()
        m = hashlib.md5("%s-ok%s" % (entity_id, r))
        session_id = m.hexdigest()
        self._db.execute("""
        INSERT INTO [:table schema=cerebrum name=bofhd_session]
          (session_id, account_id, auth_time, last_seen, ip_address)
        VALUES (:session_id, :account_id, [:now], [:now], :ip_address)""", {
            'session_id': session_id,
            'account_id': entity_id,
            'ip_address': ip_to_long(ip_address),
            })
        self._entity_id = entity_id
        self._id = session_id
        return self.get_session_id()

    def get_session_id(self):
        """ Return session_id that self is bound to.  """
        if self._id is None:
            return self._id

        # IVR 2010-04-22: We want to always force session_id to be a string.
        # I.e. this function must not return anything else, so that
        # BofhdSession's users can rely on the session being a string.
        return str(self._id)

    def get_entity_id(self, include_expired=False):
        """ Get the entity_id of the user that owns this session.

        :param boolean include_expired:
            If we should accept a session that is expired (default: False).

        :rtype: int
        :return: The entity id of the session owner.

        :raises RuntimeError:
            If this session does not have a session_id.
        :raises SessionExpiredError:
            If the session does not exist (in the database), or has timed out.
            Note: If include_expired is True, we won't raise this exception for
            timed out sessions.

        """
        if self.get_session_id() is None:
            # TBD: Proper exception class?
            raise RuntimeError("Unable to get entity_id; "
                               "not associated with any session.")
        if self._entity_id is not None:
            return self._entity_id

        binds = {'session_id': self.get_session_id(), }

        not_expired_clause = ''
        if include_expired is False:
            not_expired_clause = ('AND auth_time >= :auth '
                                  'AND last_seen >= :seen')
            binds['auth'] = self._get_timeout_timestamp('auth')
            binds['seen'] = self._get_timeout_timestamp('seen')

        try:
            self._entity_id = self._db.query_1("""
            SELECT account_id
            FROM [:table schema=cerebrum name=bofhd_session]
            WHERE session_id=:session_id %s""" % not_expired_clause, binds)

            # Log that there was an activity from the client.
            self._db.execute("""
            UPDATE [:table schema=cerebrum name=bofhd_session]
            SET last_seen=[:now]
            WHERE session_id=:session_id""",
                             {'session_id': self.get_session_id()})
        except NotFoundError:
            raise errors.SessionExpiredError(
                "Authentication failure: session expired. "
                "You must login again")
        return self._entity_id

    def _fetch_account(self, account_id):
        """ Get a populated Acccount object. """
        ac = Utils.Factory.get('Account')(self._db)
        ac.find(account_id)
        return ac

    def get_owner_id(self):
        if self._owner_id is None:
            account_id = self.get_entity_id()
            self._owner_id = int(self._fetch_account(account_id).owner_id)
        return self._owner_id

    def store_state(self, state_type, state_data, entity_id=None):
        """Add state tuple to ``session_id``."""
        # TODO: assert that there is space for state_data
        return self._db.execute(
            """
            INSERT INTO [:table schema=cerebrum name=bofhd_session_state]
            (session_id, state_type, entity_id, state_data, set_time)
            VALUES (:session_id, :state_type, :entity_id, :state_data, [:now])
            """,
            {'session_id': self.get_session_id(),
             'state_type': state_type,
             'entity_id': entity_id,
             'state_data': json.dumps(state_data, ensure_ascii=False)})

    def get_state(self, state_type=None):
        """Retrieve all state tuples for ``session_id``."""
        if state_type is not None:
            where = "AND state_type=:state_type"
        else:
            where = ""
        ret = self._db.query("""
        SELECT state_type, entity_id, state_data, set_time
        FROM [:table schema=cerebrum name=bofhd_session_state]
        WHERE session_id=:session_id %s
        ORDER BY set_time""" % where, {
            'session_id': self.get_session_id(),
            'state_type': state_type})
        for r in ret:
            try:
                r['state_data'] = json.loads(r['state_data'])
            except:
                r['state_data'] = None
                self.logger.warn('Invalid state data for session id:'
                                 ' {session_id}. Cleaning state'.format(
                                     session_id=self.get_session_id()))
                self.clear_state()
        return ret

    def clear_state(self, state_types=None):
        """ Remove session state data.

        Session state data mainly constists of cached passwords for the
        misc_list_passwords command.
        """
        sql = """DELETE FROM [:table schema=cerebrum name=bofhd_session_state]
                 WHERE session_id=:session_id"""
        binds = {'session_id': self.get_session_id()}
        if state_types:
            sql += " AND " + Utils.argument_to_sql(
                state_types, 'state_type', binds, str)

        self._db.execute(sql, binds)
        self._remove_old_sessions()
    # end clear_state

    def clear_session(self):
        """ Remove session. """
        sql = """DELETE FROM [:table schema=cerebrum name=bofhd_session]
                 WHERE session_id=:session_id"""
        binds = {'session_id': self.get_session_id()}
        self.clear_state()
        self._db.execute(sql, binds)

    def reassign_session(self, target_id):
        """Reassociate a new entity with current session key.

        This method is the equivalent of UNIX' 'su'. We substitute current
        session owner with target_id.

        All the following commands in bofhd will be executed with the
        permissions of target_id. Do not use this method lightly!

        @type target_id: int
        @param target_id:
          Account id for the new session owner for *this* session
          (i.e. self._id)
        """
        old_session_owner = self._entity_id
        self._entity_id = target_id
        try:
            # Change the session owner
            # Log that there was an activity from the client.
            self._db.execute("""
            UPDATE [:table schema=cerebrum name=bofhd_session]
            SET last_seen=[:now], account_id=:account_id
            WHERE session_id=:session_id""",
                             {'account_id': target_id,
                              'session_id': self._id})
        except NotFoundError:
            raise errors.SessionExpiredError(
                "Failed to reassign session. Try to login again?")

        self._owner_id = self.get_owner_id()
        self.logger.info("Changed session=%s entity %s (id=%s) -> %s (id=%s)",
                         self._id,
                         self._fetch_account(old_session_owner).account_name,
                         old_session_owner,
                         self._fetch_account(self._entity_id).account_name,
                         self._entity_id)
