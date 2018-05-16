#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2012 University of Oslo, Norway
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
"""The part of CIS which handles authentication of Services, in addition to
access control. The access control is mostly a wrapper around BofhdAuth that
was originally used by bofhd.

Authentication
--------------

To add authentication for all public methods in a Service class::

    from Cerebrum.modules.cis import SoapListener, auth

    class NewService(SoapListener.BasicSoapServer):
        '''Your Service class that requires authentication'''

        # The session ID is put in the SOAP headers, and is required for the
        # authentication functionality:
        __in_header__ = SoapListener.SessionHeader

        # All your public methods here

    # Add auth events to the service:

    # This will check if the client is authenticated and raise
    # NotAuthenticatedErrors for everyone that are not authenticated.
    NewService.event_manager.add_listener('method_call',
        auth.on_method_authentication)

    # ...

    # Add the proper auth service to the list of services, to make the auth
    # methods callable (otherwise you would never be able to authenticate).
    services = [auth.PasswordAuthenticationService, NewService]
    server = SoapListener.TwistedSoapStarter(applications = services, ...)
    server.run()

TODO: add documentation for how to only require authentication for single
public methods.

Access control
--------------

It is recommended to check the authorizations in the cerebrum specific
classes, and not in the service classes. The reason is that we could find out
more about the operator and the environment when we're in the Cerebrum class.

To support access control, simply make use of BofhdAuth in the same way as for
the bofh daemon. CIS handles the exceptions from BofhdAuth and gives the
client proper error messages.

TODO: It might be necessary to create own BofhdAuth classes that has CIS
specific functionality in the future. Don't know were it should be put, but
probably not here.

To support access control, add the following to your Cerebrum class:

    from Cerebrum.modules.bofhd.auth import BofhdAuth
    from Cerebrum.modules.bofhd.errors import PermissionDenied

    class CerebrumFunctions(object):
        __init__(self, operator_id):
            self.auth = BofhdAuth(self.db)
            self.operator_id = operator_id

        def get_something(self, data):
            # This could raise PermissionDenied, which is then handled by CIS:
            self.auth.can_access_data(self.operator_id, data)
            ...

"""

from __future__ import unicode_literals

from mx import DateTime

from twisted.python import log

from rpclib.model.primitive import Unicode
from rpclib.decorator import rpc

import cereconf
from Cerebrum import Errors
from Cerebrum import QuarantineHandler
from Cerebrum.Utils import Factory
from Cerebrum.modules.cis import SoapListener
from Cerebrum.modules.cis.faults import (AuthenticationError,
                                         NotAuthenticatedError)


class Authenticator(object):
    """Class for handling an authenticated entity. Could be subclassed for more
    functionality, e.g. other timeouts.

    """
    def __init__(self, id):
        """Feed the authenticator instance with the identifier of the
        authenticated entity."""
        if not id:
            raise AuthenticationError('Empty identitifer is not allowed')
        self.authenticated = True
        self.id = id
        self.started = DateTime.now()
        self.lastAccessed = DateTime.now()
        # TODO: more data we would need?

    def expire(self):
        """Deauthenticate, log out."""
        self.authenticated = False
        self.id = None

    def expired(self):
        """Check if the authentication has expired. This could be subclassed to
        support different ways of expiration."""
        if not self.authenticated:
            return True
        # TODO: add some expiration checking of the start timestamp, or do we
        # only trust twisted's session timeout?
        return False


class AuthenticationService(SoapListener.BasicSoapServer):
    """A generic authentication service. Subclass it to support different ways
    of authenticating.

    Please note that subclassing doesn't work in the standard way here, as the
    class is not instantiated. Instead, the L{ctx} instance refers to
    L{ctx.service_class}. This is why the authentication method is not created
    in this class, but has to be defined in the subclasses instead, and should
    call the static function _authenticate.

    TODO: there is probably a cleaner way to solve the subclassing here.

    """

    __in_header__ = SoapListener.SessionHeader

    __out_header__ = SoapListener.SessionHeader

    # What class to use for the authentication data
    authenticatorFactory = Authenticator

    # TODO this is a hack, check if these attributes are needed
    site = None

    @staticmethod
    def _authenticate(ctx, id):
        """
        The method for setting the authenticate values. Should only be called
        internally by an Auth Service that has authenticated a client/user
        properly. This method blindly accepts an entity as authenticated.

        Note that we use twisted's session, which e.g. handles timeouts
        automatically. Be aware that this method creates a new session, as it
        is a security risk to reuse the old session due to session fixation
        attacks. This is mostly important for web browsers, but still.

        @type id: string or mixed
        @param id: An identifier of the authenticated client, user or any
            entity. Could for instance be its username.

        """
        log.msg('DEBUG: Authenticated entity_id:%s' % id)
        old = ctx.udc['session']
        # creates a new session to use
        new = ctx.service_class.site.makeSession()
        for key in old:
            new[key] = old[key]
            # TODO: create a __copy__ in our SessionCacher to use instead
        new['authenticated'] = ctx.service_class.authenticatorFactory(id)
        ctx.udc['session'] = new
        new.touch()
        old.expire()
        return new

    @staticmethod
    def _deauthenticate(ctx):
        """Call this for deauthenticating from the session, i.e. logging out of
        this service.
        """
        auth = ctx.udc['session'].get('authenticated', None)
        if auth:
            log.msg("DEBUG: deauthenticating: %s" % auth.id)
            auth.expire()
            del ctx.udc['session']['authenticated']


AuthenticationService.event_manager.add_listener(
    'method_call', SoapListener.on_method_call_session)

AuthenticationService.event_manager.add_listener(
    'method_return_object', SoapListener.on_method_exit_session)


class PasswordAuthenticationService(AuthenticationService):
    """Authentication Service where the auth is handled by username and
    passwords.
    """
    # Standard message to return in case of errors:
    error_msg = 'Unknown username or password'

    @rpc(Unicode, Unicode, _returns=Unicode, _throws=AuthenticationError)
    def authenticate(ctx, username, password):
        """The authentication method, as some methods require you to be
        authenticated before use. Please add your username and password.

        @type username: Unicode
        @param username: Your username. The user must exist in Cerebrum.

        @type password: Unicode
        @param password: Your password.

        @rtype: Unicode
        @return:
            The new authenticated session ID. It is also available in the
            returned SOAP headers, as session_id.
        """
        if not username or not password:
            raise AuthenticationError(ctx.service_class.error_msg)

        # TODO: should add some short, random delay at startup, to avoid
        # letting people know what went wrong, e.g. if a username exists or
        # not.

        # TODO: need to limit brute force attacks somehow, e.g. block per IP.

        db = Factory.get('Database')()
        account = Factory.get('Account')(db)
        constant = Factory.get('Constants')(db)
        try:
            account.find_by_name(username)
        except Errors.NotFoundError:
            log.msg("INFO: auth: no such user: %s" % username)
            # Close the database-connection
            db.close()
            raise AuthenticationError(ctx.service_class.error_msg)

        # TODO: bofhd.py's bofhd_login has much functionality - put much of it
        # into the Account class to be able to use same code in both places?
        # For instance::
        #
        #   ac.find_by_name(username) # could raise exception
        #   ac.authenticate(password) # could raise exception
        #
        # If success, we could create session etc.
        # Check quarantines
        quarantines = []
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
                if not str(constant.Quarantine(qrow['quarantine_type'])) \
                       in cereconf.BOFHD_NONLOCK_QUARANTINES:
                    quarantines.append(qrow['quarantine_type'])
        qh = QuarantineHandler.QuarantineHandler(db, quarantines)
        if qh.should_skip() or qh.is_locked():
            qua_repr = ", ".join(constant.Quarantine(q).description
                                 for q in quarantines)
            log.msg("INFO: user has active quarantine. Access denied: %s"
                    % qua_repr)
            # Close the database-connection
            db.close()
            raise AuthenticationError(ctx.service_class.error_msg)
        # User exists here, check password
        if not account.verify_auth(password):
            # Close the database-connection
            db.close()
            log.msg("INFO: Failed login for %s." % username)
            raise AuthenticationError(ctx.service_class.error_msg)
        ses = ctx.service_class._authenticate(ctx, account.entity_id)
        return ses.uid

    @rpc()
    def deauthenticate(ctx):
        """Logs out of the service. No input is needed, makes use of the
        session id in the SOAP headers.

        """
        ctx.service_class._deauthenticate(ctx)


class UsernameAuthenticationService(AuthenticationService):
    """Authentication Service where the auth is handled by username only.

    When using this service you are trusting the security of your client.
    """
    # Standard message to return in case of errors:
    error_msg = 'Unknown username'

    @rpc(Unicode, _returns=Unicode, _throws=AuthenticationError)
    def authenticate(ctx, username):
        """The authentication method, as some methods require you to be
        authenticated before use.

        @type username: Unicode
        @param username: Your username. The user must exist in Cerebrum.

        @rtype: Unicode
        @return:
            The new authenticated session ID. It is also available in the
            returned SOAP headers, as session_id.
        """
        if not username:
            raise AuthenticationError(ctx.service_class.error_msg)

        db = Factory.get('Database')()
        account = Factory.get('Account')(db)
        constant = Factory.get('Constants')(db)
        try:
            account.find_by_name(username)
        except Errors.NotFoundError:
            log.msg("INFO: auth: no such user: %s" % username)
            raise AuthenticationError(ctx.service_class.error_msg)

        # Check quarantines
        quarantines = []
        for qrow in account.get_entity_quarantine(only_active=True):
                if not str(constant.Quarantine(qrow['quarantine_type'])) \
                       in cereconf.BOFHD_NONLOCK_QUARANTINES:
                    quarantines.append(qrow['quarantine_type'])
        qh = QuarantineHandler.QuarantineHandler(db, quarantines)
        if qh.should_skip() or qh.is_locked():
            qua_repr = ", ".join(constant.Quarantine(q).description
                                 for q in quarantines)
            log.msg("INFO: user has active quarantine. Access denied: %s"
                    % qua_repr)
            raise AuthenticationError(ctx.service_class.error_msg)

        # User exists, let's authenticate it
        ses = ctx.service_class._authenticate(ctx, account.entity_id)
        return ses.uid

    @rpc()
    def deauthenticate(ctx):
        """Logs out of the service. No input is needed, makes use of the
        session id in the SOAP headers.

        """
        ctx.service_class._deauthenticate(ctx)


#
# Events
#
def on_method_authentication(ctx):
    """Event for checking that the client is authenticated before calling a
    method. This event should be added to every Service class that require
    authentication."""
    log.msg('DEBUG: on_authentication')
    try:
        auth = ctx.udc['session']['authenticated']
        log.msg('DEBUG: auth_%s' % auth.id)
        if not auth.expired():
            return True
    except KeyError:
        pass
    log.msg('INFO: Not authenticated')
    raise NotAuthenticatedError()
