#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2002-2014 University of Oslo, Norway
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

# $Id$

#
# Server used by clients that wants to access the cerebrum database.
#
# Work in progress, current implementation, expect big changes
#

import sys
import crypt
import hashlib
import re
import socket
import struct
import types

import cerebrum_path
import cereconf
if sys.version_info < (2, 3):
    from Cerebrum.extlib import timeoutsocket
    use_new_timeout = False
else:
    use_new_timeout = True
    # Doesn't work with m2crypto:
    # socket.setdefaulttimeout(cereconf.BOFHD_CLIENT_SOCKET_TIMEOUT)
import thread
import threading
import time
import pickle
import SocketServer
import SimpleXMLRPCServer
import xmlrpclib
import getopt
from random import Random

try:
    from M2Crypto import SSL
    CRYPTO_AVAILABLE = True
    # Turn off m2crypto ssl chatter. These flags are NOT documented anywhere
    # in m2crypto, so use with care :)
    import M2Crypto
    M2Crypto.m2.SSL_CB_LOOP = 0
    M2Crypto.m2.SSL_CB_EXIT = 0
except ImportError:
    CRYPTO_AVAILABLE = False

# import SecureXMLRPCServer

from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum import QuarantineHandler
from Cerebrum.modules.bofhd.errors import CerebrumError, \
    UnknownError, ServerRestartedError, SessionExpiredError
from Cerebrum.modules.bofhd.help import Help
from Cerebrum.modules.bofhd.xmlutils import \
     xmlrpc_to_native, native_to_xmlrpc
from Cerebrum.modules.bofhd.utils import BofhdUtils

Account_class = Utils.Factory.get('Account')

# An installation *may* have many instances of bofhd running in parallel. If
# this is the case, make sure that all of the instances get their own
# logger. Otherwise, depending on the logger used, the physical entity
# representing the log (typically a file) may not cope with multiple processes
# writing to it simultaneously.
logger = Utils.Factory.get_logger("bofhd")  # The import modules use the "import" logger


# This regex is too permissive for IP-addresses, but that does not matter,
# since we use a library function that traps non-sensical values.
_subnet_rex = re.compile(r"((\d+)\.(\d+)\.(\d+)\.(\d+))\/(\d+)")
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
# end ip_subnet_slash_to_range

def ip_to_long(ip_address):
    """Convert IP address in string notation to a 4 byte long.

    @type ip_address: basestring
    @param ip_address:
      IP address to convert in A.B.C.D notation
    """

    return struct.unpack("!L", socket.inet_aton(ip_address))[0]
# end ip_to_long


class BofhdSession(object):

    """ Handle database sessions for the BofhdServer.

    This object is used to store and retrieve sessions from the database, which
    in turn is used to validate session_ids from clients.

    A session_id is valid if it (a) exists in the database, and (b) is not
    timed out. A session can time out in two ways:

    If a certain time passes from the last time the client authenticated with a
    username and password, the session is invalidated. The authentication
    timeout is controlled by the _auth_timeout attribute.

    The session tracks the last time an action was performed. If a certain time
    passes from the last action (the client is idle), the session is also
    invalidated.

    The idle timeout is controlled by attributes _seen_timeout and
    _short_timeout. The _short_timeout attribute applies to hosts in the
    _short_timeout_hosts attribute, and is intended for web clients and other
    clients that should not keep an idle session for too long.

    """

    def _get_short_timeout():
        """ Get the shorter timeout for the short timeout hosts.

        This method fetches and validates the BOFHD_SHORT_TIMEOUT cereconf
        setting. The shorter timeout is used for hosts fetched by
        L{_get_short_timeout_hosts}.

        """
        if hasattr(cereconf, "BOFHD_SHORT_TIMEOUT"):
            timeout = int(cereconf.BOFHD_SHORT_TIMEOUT)
            if not (60 <= timeout <= 3600*24):
                raise ValueError("Bogus BOFHD_SHORT_TIMEOUT timeout: %ss"
                                 % cereconf.BOFHD_SHORT_TIMEOUT)
            logger.debug("Short-lived sessions expire after %ds",
                         timeout)
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
                    hosts.append((low, high))
                    logger.debug("Sessions from subnet %s [%s, %s] "
                                 "will be short-lived", ip, low, high)
                # It's a simple IP-address
                else:
                    addr_long = ip_to_long(ip)
                    hosts.append((addr_long, addr_long))
                    logger.debug("Sessions from IP %s [%s, %s] will be "
                                 "short-lived", ip, addr_long, addr_long)
        return hosts

    _auth_timeout = 3600*24*7
    """ In seconds, how long a session should live after authentication. """

    _seen_timeout = 3600*24
    """ In seconds, how long a session should 'idle'. """

    _short_timeout = _get_short_timeout()
    """ In seconds, how long a session should 'idle' for certain clients. """

    _short_timeout_hosts = _get_short_timeout_hosts()
    """ Which clients should have the shorter timeout setting. """

    def __init__(self, database, session_id=None, remote_address=None):
        """ Create a new session.

        :param Database database: A database connection.
        :param str session_id: The session_id for this session.
        :param str remote_address: The IP of the client for this session.

        """
        self._db = database
        if not isinstance(session_id, (types.NoneType, str, unicode)):
            raise CerebrumError("Wrong session id type: %s,"
                                " expected str or None" % type(session_id))
        self._id = str(session_id)
        self._entity_id = None
        self._owner_id = None
        self.remote_address = remote_address

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
        for index, (ip_start, ip_stop) in enumerate(self._short_timeout_hosts):
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
            f = open('/dev/urandom')
            r = f.read(48)
        except IOError:
            r = Random().random()
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
        except Errors.NotFoundError:
            raise SessionExpiredError("Authentication failure: "
                                      "session expired. You must login again")
        return self._entity_id

    def _fetch_account(self, account_id):
        """ Get a populated Acccount object. """
        ac = Account_class(self._db)
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
        return self._db.execute("""
        INSERT INTO [:table schema=cerebrum name=bofhd_session_state]
          (session_id, state_type, entity_id, state_data, set_time)
        VALUES (:session_id, :state_type, :entity_id, :state_data, [:now])""",
                                {'session_id': self.get_session_id(),
                                 'state_type': state_type,
                                 'entity_id': entity_id,
                                 'state_data': pickle.dumps(state_data), })

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
            r['state_data'] = pickle.loads(r['state_data'])
        return ret

    def clear_state(self, state_types=None):
        """ Remove session state data.

        Session state data mainly constists of cached passwords for the
        misc_list_passwords command.

        """
        if state_types is None:
            state_types = ('*',)
        for state in state_types:
            sql = """
            DELETE FROM [:table schema=cerebrum name=bofhd_session_state]
            WHERE session_id=:session_id
            """
            if state != '*':
                sql += " AND state_type=:state"
            self._db.execute(sql, {'session_id': self.get_session_id(),
                                   'state': state})
            if state == '*':
                self._db.execute("""
                DELETE FROM [:table schema=cerebrum name=bofhd_session]
                WHERE session_id=:session_id
                """, {'session_id': self.get_session_id()})
        self._remove_old_sessions()
    # end clear_state


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
        except Errors.NotFoundError:
            raise SessionExpiredError("Failed to reassign session. "
                                      "Try to login again?")

        self._owner_id = self.get_owner_id()
        logger.info("Changed session=%s entity %s (id=%s) -> %s (id=%s)",
                    self._id,
                    self._fetch_account(old_session_owner).account_name,
                    old_session_owner,
                    self._fetch_account(self._entity_id).account_name,
                    self._entity_id)
    # end reassign_session
# end BofhdSession



class BofhdRequestHandler(SimpleXMLRPCServer.SimpleXMLRPCRequestHandler,
                          object):

    """Class defining all XML-RPC-callable methods.

    These methods can be called by anyone with access to the port that
    the server is running on.  Care must be taken to validate input.

    """

    use_encryption = CRYPTO_AVAILABLE

    def _dispatch(self, method, params):
        try:
            func = getattr(self, 'bofhd_' + method)
        except AttributeError:
            raise Exception('method "%s" is not supported' % method)
        try:
            ret = apply(func, xmlrpc_to_native(params))
        except CerebrumError, e:
            # Exceptions with unicode characters in the message
            # produce a UnicodeError when cast to str().  Fix by
            # encoding as utf-8
            if e.args:
                ret = "%s: %s" % (e.__class__.__name__, e.args[0])
            else:
                ret = e.__class__.__name__
            if isinstance(ret, unicode):
                raise CerebrumError(ret.encode('utf-8'))
            else:
                # Some of our exceptions throws iso8859-1 encoded
                # error-messages.  These must be encoded as utf-8 to
                # avoid client-side:
                #   org.xml.sax.SAXParseException: character not allowed
                ret = ret.decode('iso8859-1').encode('utf-8')
                raise CerebrumError(ret)
        except NotImplementedError, e:
            logger.warn("Not-implemented: ", exc_info=1)
            raise CerebrumError("Not Implemented: %s" % str(e))
        except TypeError, e:
            if (str(e).find("takes exactly") != -1
                    or str(e).find("takes at least") != -1
                    or str(e).find("takes at most") != -1):
                raise CerebrumError(str(e))
            logger.warn("Unexpected exception", exc_info=1)
            raise UnknownError(sys.exc_info()[0],
                               sys.exc_info()[1],
                               msg="A server error has been logged.")
        except Exception, e:
            logger.warn("Unexpected exception", exc_info=1)
            raise UnknownError(sys.exc_info()[0],
                               sys.exc_info()[1],
                               msg="A server error has been logged.")
        return native_to_xmlrpc(ret)

    def handle(self):
        if not use_new_timeout:
            if not use_encryption:
                self.connection.set_timeout(cereconf.BOFHD_CLIENT_SOCKET_TIMEOUT)
            try:
                super(BofhdRequestHandler, self).handle()
            except timeoutsocket.Timeout, msg:
                logger.debug("Timeout: %s from %s" % (
                    msg, ":".join([str(x) for x in self.client_address])))
                self.server.db.rollback()
        else:
            if not use_encryption:
                self.connection.settimeout(cereconf.BOFHD_CLIENT_SOCKET_TIMEOUT)
            try:
                super(BofhdRequestHandler, self).handle()
            except socket.timeout, msg:
                logger.debug("Timeout: %s from %s" % (
                    msg, ":".join([str(x) for x in self.client_address])))
                self.server.db.rollback()

    # This method is pretty identical to the one shipped with Python,
    # except that we don't silently eat exceptions
    def do_POST(self):
        """Handles the HTTP POST request.

        Attempts to interpret all HTTP POST requests as XML-RPC calls,
        which are forwarded to the _dispatch method for handling.
        """

        # Whenever unexpected exception occurs, we'd like to include
        # as much debugging info as possible.  To avoid raising
        # NameError in the debug-printing code, we pre-initialise a
        # few central variables.
        data = params = method = None
        try:
            # get arguments
            data = self.rfile.read(int(self.headers["content-length"]))
            params, method = xmlrpclib.loads(data)

            # generate response
            try:
                logger.debug2(
                    "[%s] dispatch %s" % (threading.currentThread().getName(), method))

                response = self._dispatch(method, params)
                # wrap response in a singleton tuple
                response = (response,)
            except CerebrumError:
                # Due to the primitive XML-RPC support for exceptions,
                # we want to report any subclass of CerebrumError as
                # CerebrumError so that the client can recognize this
                # as a user-error.
                # TODO: This is not a perfect solution...
                if sys.exc_type in (ServerRestartedError,
                                    SessionExpiredError,
                                    UnknownError):
                    error_class = sys.exc_type
                else:
                    error_class = CerebrumError
                response = xmlrpclib.dumps(
                    xmlrpclib.Fault(1, "%s.%s:%s" % (error_class.__module__,
                                                     error_class.__name__,
                                                     sys.exc_value)))
            except:
                logger.warn(
                    "Unexpected exception 1 (client=%r, params=%r, method=%r)",
                    self.client_address, params, method,
                    exc_info=True)
                # report exception back to server
                response = xmlrpclib.dumps(
                    xmlrpclib.Fault(1, "%s:%s" % (sys.exc_type,
                                                  sys.exc_value)))
            else:
                response = xmlrpclib.dumps(response, methodresponse=1)
        except:
            logger.warn("Unexpected exception 2 (client %r, data=%r)",
                        self.client_address, data,
                        exc_info=True)
            # internal error, report as HTTP server error
            self.send_response(500)
            self.end_headers()
        else:
            # got a valid XML RPC response
            self.send_response(200)
            self.send_header("Content-type", "text/xml")
            self.send_header("Content-length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

            # shut down the connection
            self.wfile.flush()
            self.connection.shutdown(1)
        logger.debug2("End of" + threading.currentThread().getName())

    def finish(self):
        if self.use_encryption:
            self.request.set_shutdown(SSL.SSL_RECEIVED_SHUTDOWN |
                                      SSL.SSL_SENT_SHUTDOWN)
            self.request.close()
        else:
            super(BofhdRequestHandler, self).finish()

    def bofhd_login(self, uname, password):
        account = Account_class(self.server.db)
        try:
            account.find_by_name(uname)
        except Errors.NotFoundError:
            if isinstance(uname, unicode):
                uname = uname.encode('utf-8')
            logger.info("Failed login for %s from %s" % (
                uname, ":".join([str(x) for x in self.client_address])))
            raise CerebrumError("Unknown username or password")

        # Check quarantines
        quarantines = []      # TBD: Should the quarantine-check have a utility-API function?
        for qrow in account.get_entity_quarantine(only_active=True):
                # The quarantine found in this row is currently
                # active. Some quarantine types may not restrict
                # access to bofhd even if they otherwise result in
                # lock. Check therefore whether a found quarantine
                # should be appended
                #
                # FIXME, Jazz 2008-04-08:
                # This should probably be based on spreads or some
                # such mechanism, but quarantinehandler and the import
                # routines don't support a more appopriate solution yet
                if not str(self.server.const.Quarantine(qrow['quarantine_type'])) \
                       in cereconf.BOFHD_NONLOCK_QUARANTINES:
                    quarantines.append(qrow['quarantine_type'])            
        qh = QuarantineHandler.QuarantineHandler(self.server.db,
                                                 quarantines)
        if qh.should_skip() or qh.is_locked():
            qua_repr = ", ".join(self.server.const.Quarantine(q).description
                                 for q in quarantines)
            raise CerebrumError("User has active lock/skip quarantines, login denied:"
                                " %s" % qua_repr)
        # Check expire_date
        if account.is_expired():
            raise CerebrumError("User is expired")
        # Check password
        enc_passwords = []
        for auth in (self.server.const.auth_type_md5_crypt,
                     self.server.const.auth_type_crypt3_des):
            try:
                enc_pass = account.get_account_authentication(auth)
                if enc_pass:            # Ignore empty password hashes
                    enc_passwords.append(enc_pass)
            except Errors.NotFoundError:
                pass
        if not enc_passwords:
            logger.info("Missing password for %s from %s" % (uname,
                        ":".join([str(x) for x in self.client_address])))
            raise CerebrumError("Unknown username or password")
        if isinstance(password, unicode):  # crypt.crypt don't like unicode
            # TODO: ideally we should not hardcode charset here.
            password = password.encode('iso8859-1')
        # TODO: Add API for credential verification to Account.py.
        mismatch = map(lambda e: e != crypt.crypt(password, e), enc_passwords)
        if filter(None, mismatch):
            # Use same error message as above; un-authenticated
            # parties should not be told that this in fact is a valid
            # username.
            if filter(lambda m: not m, mismatch):
                mismatch = zip(mismatch, enc_passwords)
                match    = [p[1] for p in mismatch if not p[0]]
                mismatch = [p[1] for p in mismatch if p[0]]
                if filter(lambda c: c < '!' or c > '~', password):
                    chars = 'chars, including [^!-~]'
                else:
                    chars = 'good chars'
                logger.info("Password (%d %s) for user %s matches"
                            " auth_data '%s' but not '%s'"
                            % (len(password), chars, uname,
                               "', '".join(match), "', '".join(mismatch)))
            logger.info("Failed login for %s from %s" % (
                uname, ":".join([str(x) for x in self.client_address])))
            raise CerebrumError("Unknown username or password")
        try:
            logger.info("Succesful login for %s from %s" % (
                uname, ":".join([str(x) for x in self.client_address])))
            session = BofhdSession(self.server.db)
            session_id = session.set_authenticated_entity(account.entity_id,
                                                          self.client_address[0])
            self.server.db.commit()
            self.server.known_sessions[session_id] = 1
            return session_id
        except Exception:
            self.server.db.rollback()
            raise

    def bofhd_logout(self, session_id):
        session = BofhdSession(self.server.db, session_id)
        try:
            session.clear_state()
            if self.server.known_sessions.has_key(session_id):
                del(self.server.known_sessions[session_id])
            self.server.db.commit()
        except Exception:
            self.server.db.rollback()
            raise
        return "OK"

    def bofhd_get_commands(self, session_id):
        """Build a dict of the commands available to the client."""

        session = BofhdSession(self.server.db, session_id)
        entity_id = session.get_entity_id()
        commands = {}
        for inst in self.server.cmd_instances:
            newcmd = inst.get_commands(entity_id)
            for k in newcmd.keys():
                if inst is not self.server.cmd2instance[k]:
                    # If module B is imported after module A, and both
                    # implement 'command', only the implementation in
                    # the latter module will actually be callable.
                    #
                    # However, A.get_commands() and B.get_commands()
                    # might not agree on whether or not the
                    # authenticated user should be allowed to invoke
                    # 'command'.
                    #
                    # Hence, to avoid including overridden,
                    # non-callable functions in our return value, we
                    # verify that the module in
                    # self.command2module[command] matches the module
                    # whose .get_commands() we're processing.
                    logger.info("Skipping: %s" % k)
                    continue
                commands[k] = newcmd[k]
        return commands

    def bofhd_get_format_suggestion(self, cmd):
        suggestion = self.server.cmd2instance[cmd].get_format_suggestion(cmd)
        if suggestion is not None:
            # suggestion['str'] = unicode(suggestion['str'], 'iso8859-1')
            pass
        else:
            # TODO:  Would be better to allow xmlrpc-wrapper to handle None
            return ''
        return suggestion

    def bofhd_get_motd(self, client_id=None, client_version=None):
        ret = ""
        if cereconf.BOFHD_MOTD_FILE is not None:
            f = file(cereconf.BOFHD_MOTD_FILE)
            for line in f.readlines():
                ret += line
        if (client_id is not None and
                cereconf.BOFHD_CLIENTS.get(client_id, '') > client_version):
            ret += "You do not seem to run the latest version of the client\n"
        return ret[:-1]

    def bofhd_help(self, session_id, *group):
        logger.debug("Help: %s" % str(group))
        commands = self.bofhd_get_commands(session_id)
        if len(group) == 0:
            ret = self.server.help.get_general_help(commands)
        elif group[0] == 'arg_help':
            ret = self.server.help.get_arg_help(group[1])
        elif len(group) == 1:
            ret = self.server.help.get_group_help(commands, *group)
        elif len(group) == 2:
            ret = server.help.get_cmd_help(commands, *group)
        else:
            raise CerebrumError("Unexpected help request")
        return ret

    def _run_command_with_tuples(self, func, session, args, myret):
        next_tuple = -1
        for n in range(len(args)):
            if isinstance(args[n], (tuple, list)):
                next_tuple = n
                break
        if next_tuple == -1:
            myret.append(func(session, *args))
        else:
            for x in args[next_tuple]:
                new_args = args[:next_tuple] + (x,) + args[next_tuple+1:]
                self._run_command_with_tuples(func, session, new_args, myret)


    def check_session_validity(self, session):
        """Make sure that session has not expired.

        @type session: instance of BofhdSession
        @param session: session object we are checking.

        @rtype: int
        @return:
          entity_id of the entity owning the session (i.e. which account is
          associated with that specific session_id)
        """

        session_id = session.get_session_id()
        # This is throw an exception, when session_id has expired
        entity_id = session.get_entity_id()
        if session.remote_address is None:
            session.remote_address = self.client_address

        if session_id not in self.server.known_sessions:
            self.server.known_sessions[session_id] = 1
            raise ServerRestartedError()

        return entity_id

    def bofhd_run_command(self, session_id, cmd, *args):
        """Execute the callable function (in the correct module) with
        the given name after mapping session_id to username"""

        # First, drop the short-lived sessions FIXME: if this is too
        # CPU-intensive, introduce a timestamp in this class, and drop the
        # short-lived sessions ONLY if more than BofhdSession._short_timeout
        session = BofhdSession(self.server.db)
        session.remove_short_timeout_sessions()

        session = BofhdSession(self.server.db, session_id, self.client_address)
        entity_id = self.check_session_validity(session)
        self.server.db.cl_init(change_by=entity_id)
        logger.debug("Run command: %s (%s) by %i" % (cmd, args, entity_id))
        if not self.server.cmd2instance.has_key(cmd):
            raise CerebrumError("Illegal command '%s'" % cmd)
        func = getattr(self.server.cmd2instance[cmd], cmd)

        try:
            has_tuples = False
            for x in args:
                if isinstance(x, (tuple, list)):
                    has_tuples = True
                    break
            ret = []
            self._run_command_with_tuples(func, session, args, ret)
            if not has_tuples:
                ret = ret[0]
            self.server.db.commit()
            # TBD: What should be returned if `args' contains tuple,
            # indicating that `func` should be called multiple times?
            return self.server.db.pythonify_data(ret)
        except Exception:
            self.server.db.rollback()
            raise

    def bofhd_call_prompt_func(self, session_id, cmd, *args):
        """Return a dict with information on how to prompt for a
        parameter.  The dict can contain the following keys:
        - prompt : message string
        - help_ref : reference to help for this argument
        - last_arg : if this argument is the last.  If only this key
          is present, the client will send the command as it is.
        - default : default value
        - map : maps the user-entered value to a value that
          is returned to the server, typically when user selects from
          a list.  It is a list-of lists, where the inner list is like:
          (("%5s %s", 'foo', 'bar'), return-value).  The first row is
          used as header
        - raw : don't use map after all"""

        session = BofhdSession(self.server.db, session_id, self.client_address)
        instance, cmdObj = self.server.get_cmd_info(cmd)
        self.check_session_validity(session)
        if cmdObj._prompt_func is not None:
            logger.debug("prompt_func: %s" % str(args))
            return getattr(instance, cmdObj._prompt_func.__name__)(session, *args)
        raise CerebrumError("Command %s has no prompt func" % (cmd,))
    # end bofhd_call_prompt_func


    def bofhd_get_default_param(self, session_id, cmd, *args):
        """ Get default value for a parameter.

        Returns a string. The client should append '[<returned_string>]: ' to
        its prompt.

        Will either use the function defined in the command object, or in the
        corresponding parameter object.

        """
        session = BofhdSession(self.server.db, session_id)
        instance, cmdObj = self.server.get_cmd_info(cmd)

        # If the client calls this method when no default function is defined,
        # it is a bug in the client.
        if cmdObj._default is not None:
            func = cmdObj._default
        else:
            func = cmdObj._params[len(args)]._default
            if func is None:
                return ""
        return getattr(instance, func.__name__)(session, *args)


class BofhdServerImplementation(object):
    def __init__(self, server_address=None,
                 RequestHandlerClass=BofhdRequestHandler,
                 database=None, config_fname=None, *args, **kws):
        # Calls to object.__init__ are no-ops, so this won't do
        # anything unless there are mixins (and they are placed after
        # BofhdServer in self's MRO).
        super(BofhdServerImplementation, self).__init__(
            server_address, RequestHandlerClass, *args, **kws)
        self.known_sessions = {}
        self.logRequests = False
        self.db = database
        self.util = BofhdUtils(database)
        self.config_fname = config_fname
        self.read_config()

    def read_config(self):
        self.const = Utils.Factory.get('Constants')(self.db)
        self.cmd2instance = {}
        self.server_start_time = time.time()
        if hasattr(self, 'cmd_instances'):
            for i in self.cmd_instances:
                reload(sys.modules[i.__module__])
        self.cmd_instances = []
        self.logger = logger

        config_file = file(self.config_fname)
        while True:
            line = config_file.readline()
            if not line:
                break
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # Import module and create an instance of it; update
            # mapping from command name to a class instance with a
            # method that implements that command.  This means that
            # any command's implementation can be overridden by
            # providing a new implementation in a later class.
            modfile, class_name = line.split("/", 1)
            mod = Utils.dyn_import(modfile)
            cls = getattr(mod, class_name)
            instance = cls(self)
            self.cmd_instances.append(instance)
            for k in instance.all_commands.keys():
                self.cmd2instance[k] = instance
            if hasattr(instance, "hidden_commands"):
                for k in instance.hidden_commands.keys():
                    self.cmd2instance[k] = instance
        t = self.cmd2instance.keys()
        t.sort()
        for k in t:
            if not hasattr(self.cmd2instance[k], k):
                logger.warn("Warning, function '%s' is not implemented" % k)
        self.help = Help(self.cmd_instances, logger=logger)

        # Check that the help text is okay
        # Reformat the command definitions to be suitable for the help.
        cmds_for_help = dict()
        for inst in self.cmd_instances:
            cmds_for_help.update(dict((k, cmd.get_struct(inst))
                                     for k, cmd in inst.all_commands.iteritems()
                                     if cmd and self.cmd2instance[k] == inst))
        self.help.check_consistency(cmds_for_help)

    def get_cmd_info(self, cmd):
        """Return BofhdExtension and Command object for this cmd
        """
        inst = self.cmd2instance[cmd]
        return (inst, inst.all_commands[cmd])

    # Override SocketServer.TCPServer (or subclass).
    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        super(BofhdServerImplementation, self).server_bind()

    def close_request(self, request):
        super(BofhdServerImplementation, self).close_request(request)
        # Check that the database is alive and well by creating a new
        # cursor.
        #
        # As close_request() is called without any except: in
        # SocketServer.BaseServer.handle_request(), any exception here
        # will actually cause bofhd to die.  This is probably what we
        # want to happen when a database connection unexpextedly goes
        # down; anything resembling automatic reconnection magic could
        # alter the crashed state of the database, making debugging
        # more difficult.
        self.db.ping()

class _TCPServer(SocketServer.TCPServer, object):
    "SocketServer.TCPServer as a new-style class."
    pass

class BofhdServer(BofhdServerImplementation, _TCPServer):
    """Plain non-encrypted Bofhd server.

    Constructor accepts the following arguments:

      server_address        -- (ipAddr, portNumber) tuple
      RequestHandlerClass   -- class for handling XML-RPC requests
      logRequests           -- boolean
      database              -- Cerebrum Database object
      config_fname          -- name of Bofhd config file

    """
    pass

class _ThreadingMixIn(SocketServer.ThreadingMixIn, object):
    "SocketServer.ThreadingMixIn as a new-style class."
    pass

class ThreadingBofhdServer(BofhdServerImplementation, _ThreadingMixIn,
                           _TCPServer):
    """Threaded non-encrypted Bofhd server.

    Constructor accepts the following arguments:

      server_address        -- (ipAddr, portNumber) tuple
      RequestHandlerClass   -- class for handling XML-RPC requests
      logRequests           -- boolean
      database              -- Cerebrum Database object
      config_fname          -- name of Bofhd config file

    """
    pass


if CRYPTO_AVAILABLE:
    class _SSLServer(SSL.SSLServer, object):
        "SSL.SSLServer as a new-style class."
        pass

    class SSLBofhdServer(BofhdServerImplementation, _SSLServer):
        """SSL-enabled Bofhd server.

        Constructor accepts the following arguments:

          server_address        -- (ipAddr, portNumber) tuple
          RequestHandlerClass   -- class for handling XML-RPC requests
          logRequests           -- boolean
          database              -- Cerebrum Database object
          config_fname          -- name of Bofhd config file
          ssl_context           -- SSL.Context object

        """
        pass

    class _ThreadingSSLServer(SSL.ThreadingSSLServer, object):
        "SSL.ThreadingSSLServer as a new-style class."
        pass

    # TODO: Check if it is sufficient to do something like:
    # class ThreadingSSLBofhdServer(SSL.ThreadingSSLServer, SSLBofhdServer)
    class ThreadingSSLBofhdServer(BofhdServerImplementation,
                                  _ThreadingSSLServer):
        """SSL-enabled threaded Bofhd server.

        Constructor accepts the following arguments:

          server_address        -- (ipAddr, portNumber) tuple
          RequestHandlerClass   -- class for handling XML-RPC requests
          logRequests           -- boolean
          database              -- Cerebrum Database object
          config_fname          -- name of Bofhd config file
          ssl_context           -- SSL.Context object

        """
        pass


_db_pool_lock = thread.allocate_lock()

class ProxyDBConnection(object):

    """ProxyDBConnection asserts that each thread gets its own
    instance of the class specified in __init__.  We maintain a pool
    of such class-objects, so that we may re-use the object when the
    thread it belonged to has terminated.

    The class works by overriding __getattr__.  Thus, when one says
    db.<anything>, this method is called.
    """

    def __init__(self, obj_class):
        self._obj_class = obj_class
        self.active_connections = {}
        self.free_pool = []

    def __getattr__(self, attrib):
        try:
            obj = self.active_connections[threading.currentThread().getName()]
        except KeyError:
            # TODO: 
            # - limit max # of simultaneously used db-connections
            # - reduce size of free_pool when size > N
            _db_pool_lock.acquire()
            logger.debug("Alloc new db-handle for " +
                         threading.currentThread().getName())
            running_threads = []
            for t in threading.enumerate():
                running_threads.append(t.getName())
            logger.debug("  Threads: " + str(running_threads))
            for p in self.active_connections.keys():
                if p not in running_threads:
                    logger.debug("  Close " + p)
                    #self.active_connections[p].close()
                    self.free_pool.append(self.active_connections[p])
                    del(self.active_connections[p])
            if not self.free_pool:
                obj = self._obj_class()
            else:
                obj = self.free_pool.pop(0)
            self.active_connections[threading.currentThread().getName()] = obj
            logger.debug("  Open: " + str(self.active_connections.keys()))
            _db_pool_lock.release()
        return getattr(obj, attrib)

def usage(exitcode=0):
    print """Usage: bofhd.py -c filename [-t keyword]
  -c | --config-file <filename>: use as config file
  -t | --test-help <keyword>: check help consistency
  -m : run multithreaded (experimental)
  -h | --host IP: listen on alternative interface (default: INADDR_ANY [0.0.0.0])
  -p | --port num: run on alternative port (default: 8000)
  --unencrypted: don't use https
"""
    sys.exit(exitcode)

if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'c:t:p:mh:',
                                   ['config-file=', 'test-help=',
                                    'port=', 'unencrypted',
                                    'multi-threaded',
                                    'host='])
    except getopt.GetoptError:
        usage(1)
        
    use_encryption = CRYPTO_AVAILABLE
    conffile = None
    host = "0.0.0.0"
    port = 8000
    multi_threaded = False
    for opt, val in opts:
        if opt in ('-c', '--config-file'):
            conffile = val
        elif opt in ('-m', '--multi-threaded'):
            multi_threaded = True
        elif opt in ('-h', '--host'):
            host = val
        elif opt in ('-p', '--port'):
            port = int(val)
        elif opt in ('-t', '--test-help'):
            # This is a bit icky.  What we want to accomplish is to
            # fetch the results from a bofhd_get_commands client
            # command.
            server = BofhdServerImplementation(
                database=Utils.Factory.get('Database')(),
                config_fname=conffile)
            commands = {}
            db = Utils.Factory.get('Database')()
            group = Utils.Factory.get('Group')(db)
            group.find_by_name(cereconf.BOFHD_SUPERUSER_GROUP)
            const = Utils.Factory.get("Constants")()
            some_superuser = [int(x["member_id"]) for x in
                              group.search_members(group_id=group.entity_id,
                                       indirect_member=True,
                                       member_type=const.entity_account)][0]
            for inst in server.cmd_instances:
                newcmd = inst.get_commands(some_superuser)
                for k in newcmd.keys():
                    if inst is not server.cmd2instance[k]:
                        print "Skipping:", k
                        continue
                    commands[k] = newcmd[k]
            if val == '':
                print server.help.get_general_help(commands)
            elif val.find(":") >= 0:
                print server.help.get_cmd_help(commands, *val.split(":"))
            elif val == 'check':
                server.help.check_consistency(commands)
            else:
                print server.help.get_group_help(commands, val)
            sys.exit()
        elif opt in ('--unencrypted',):
            use_encryption = False

    BofhdRequestHandler.use_encryption = use_encryption
            
    if conffile is None:
        usage()
        sys.exit()
        
    logger.info("Server (%s) connected to DB '%s' starting at port: %d" %
                (multi_threaded and "multi-threaded" or "single-threaded", 
                 cereconf.CEREBRUM_DATABASE_NAME, port))
    if multi_threaded:
        db = ProxyDBConnection(Utils.Factory.get('Database'))
    else:
        db = Utils.Factory.get('Database')()
    if use_encryption:
        logger.info("Server using encryption")
        # from echod_lib import init_context
        def init_context(protocol, certfile, cafile, verify, verify_depth=10):
            ctx = SSL.Context(protocol)
            ctx.load_cert(certfile)
            ctx.load_client_ca(cafile)
            ctx.load_verify_info(cafile)
            ctx.set_verify(verify, verify_depth)
            ctx.set_allow_unknown_ca(1)
            ctx.set_session_id_ctx('echod')
            ctx.set_info_callback()
            return ctx

        ctx = init_context('sslv23', '%s/server.cert' % cereconf.DB_AUTH_DIR,
                           '%s/ca.pem' % cereconf.DB_AUTH_DIR,
                           SSL.verify_none)
        ctx.set_tmp_dh('%s/dh1024.pem' % cereconf.DB_AUTH_DIR)

        if multi_threaded:
            # UiO has a locally patched M2Crypto that provides a
            # timeout mechanism for M2Crypto's SSLServer.  The easiest
            # way to detect this patch is the following look-up:
            if hasattr(SSL.Connection, "set_default_client_timeout"):
                server = ThreadingSSLBofhdServer(
                    (host, port), BofhdRequestHandler, db, conffile, ctx,
                    default_timeout=SSL.timeout(sec=4))
            else:
                server = ThreadingSSLBofhdServer(
                    (host, port), BofhdRequestHandler, db, conffile, ctx)
        else:
            if hasattr(SSL.Connection, "set_default_client_timeout"):
                server = SSLBofhdServer(
                    (host, port), BofhdRequestHandler, db, conffile, ctx,
                    default_timeout=SSL.timeout(sec=4))
            else:
                server = SSLBofhdServer(
                    (host, port), BofhdRequestHandler, db, conffile, ctx)
    else:
        logger.warning("Server *NOT* using encryption")
        if multi_threaded:
            server = ThreadingBofhdServer(
                (host, port), BofhdRequestHandler, db, conffile)
        else:
            server = BofhdServer(
                (host, port), BofhdRequestHandler, db, conffile)
    server.serve_forever()
