# coding: utf-8
#
# Copyright 2016-2026 University of Oslo, Norway
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
"""
Authentication context for a Flask app.

The auth context itself is stored in the Flask *application context*.  The
context is automatically updated by request handlers when the
:class:`Authentication` middleware is added to an application.

Configuration
--------------
This module uses settings from the Flask configuration object.  This is the
``restconfig`` module by default.

``AUTH``
    A list of authentication methods to use.

    Each entry in this list adds a :class:`.AuthModule` to use for
    authenticating users.

    Each module is processed in the order given by this setting.  The first
    module with auth data present in the request (e.g. a ``Authorization: Basic
    ...`` header for BasicAuth) will be used.


``PROXY_AUTH``
    Require basic auth from a reverse-proxy.

    This is an additional, optional layer of authentication, and is typically
    used to ensure that requests come from a trusted reverse-proxy.  This is
    disabled by default.

    See :class:`.ProxyAuth` for more details.

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import datetime
import logging
import sys
from functools import wraps

from flask import request, g
from six import python_2_unicode_compatible
from werkzeug.exceptions import Forbidden
from werkzeug.exceptions import Unauthorized as _Unauthorized

from Cerebrum import Errors
from Cerebrum.Utils import Factory, read_password
from Cerebrum.modules.apikeys.dbal import ApiMapping
from Cerebrum.utils import date_compat
from Cerebrum.utils.descriptors import lazy_property

logger = logging.getLogger(__name__)


class AuthContext(object):
    """ Authentication state for the current request.

    This is a descriptor and proxy object for the currently used AuthModule.
    It should only be used from :class:`Authentication` (or similar objects)
    to keep track of the current auth state.
    """

    OP_CLS = Factory.get('Account')
    """ Operator (account) class to use in :meth:`.get_account`. """

    def __init__(self, name):
        self.name = name

    @property
    def attr(self):
        return '_auth_ctx_{}'.format(self.name)

    def __get__(self, obj, cls=None):
        if getattr(g, self.attr, None) is None:
            setattr(g, self.attr, AuthContext(self.name))
        return getattr(g, self.attr)

    def __delete__(self, obj):
        if hasattr(g, self.attr):
            delattr(g, self.attr)

    @property
    def module(self):
        try:
            return self._module
        except AttributeError:
            return None

    @module.setter
    def module(self, m):
        try:
            del self._module
        except AttributeError:
            pass
        if not isinstance(m, AuthModule):
            raise ValueError()
        self._module = m

    @property
    def authenticated(self):
        """ True if current request is authenticated. """
        if self._module is None:
            return False
        return self._module.is_authenticated()

    @property
    def username(self):
        """ The authenticated username, if available. """
        if self.authenticated:
            return self.module.get_username()
        return None

    def get_account(self, db_ctx):
        """ The authenticated account, if available. """
        if self.authenticated:
            ac = self.OP_CLS(db_ctx.connection)
            try:
                ac.find_by_name(self.username)
                return ac
            except Errors.NotFoundError:
                pass
        return None


class Unauthorized(_Unauthorized):
    """ Unauthorized HTTP error with WWW-Authenticate data.

    >>> e = Unauthorized()
    >>> 'WWW-Authenticate' in e.get_response().headers
    False

    >>> e.realm = 'foo'
    >>> 'WWW-Authenticate' in e.get_response().headers
    True
    >>> 'Basic realm="foo"' in e.get_response().headers.get('WWW-Authenticate')
    True
    """

    realm = None

    def get_response(self, *args, **kwargs):
        response = super(Unauthorized,
                         self).get_response(*args, **kwargs)
        if self.realm is not None:
            response.www_authenticate.realm = self.realm
        return response


class Authentication(object):
    """ Authentication middleware for Flask apps. """

    ctx = AuthContext('Authentication')

    def __init__(self):
        self._modules = list()

    def init_app(self, app, db_ctx):
        self.app = app
        self.logger = app.logger
        self.db = db_ctx

        for options in app.config.get('AUTH', []):
            self.add_module(**options)

        app.before_request(self.authenticate)
        app.teardown_appcontext(self.clear)

    def add_module(self, name, *mod_args, **mod_kw):
        """Add an authentication module.

        :param string name:
            The module name

        :param bool challenge:
            If True, use this module to produce a challenge response, if no
            authentication information is given with the request.  (default:
            False)

        :param mod_args:
            Positional arguments for the module.

        :param mod_kw:
            Keyword arguments for the module.
        """
        module = self.load_module(name)
        # TODO: Implement better auth module priority:
        #   - which module to try first, which to try last?
        #   - which module to use for 401 challenge, or 403 error when multiple
        #     modules support this?
        self._modules.append(tuple((module, mod_args, mod_kw)))

    @staticmethod
    def load_module(name):
        """ Find the named authentication class. """
        if hasattr(sys.modules[__name__], name):
            return getattr(sys.modules[__name__], name)
        # TODO: Use Cerebrum.utils.module.resolve?
        raise Exception("Unknown authentication module " + name)

    def check_account(self, account):
        """ Check if account is OK. """
        if account is None:
            return False
        expire_date = date_compat.get_date(account.expire_date)
        if expire_date and expire_date < datetime.date.today():
            return False
        # TODO: Check quarantined?
        # TODO: Should we be able to whitelist certain quarantines
        return True

    def authenticate(self, *auth_args, **auth_kwargs):
        """ Perform authentication with first matched method.

        If no module succeeds auth, then the last module will be selected as
        active (e.g. for challenge / error).

        This method loops through all the authentication modules. For each
        module:

        Calling this method has four possible outcomes:

          1. No auth data in request: no user is authenticated
          2. Valid auth data in request: user is authenticated
          3. Invalid auth data in request: A Forbidden (HTTPError) is raised
          4. An unexpected exception is raised (auth fails hard, HTTP 500)

        :raise Forbidden: When an auth module fails.
        """
        for module, mod_args, mod_kw in self._modules:
            self.ctx.module = module(app=self.app, db=self.db,
                                     *mod_args, **mod_kw)
            if self.ctx.module.detect():
                # Need to log auth attempts
                self.logger.debug(
                    "Attempting auth with {}".format(type(self.ctx.module)))
                if not self.ctx.module.do_authenticate():
                    # Need to log failed login attempts
                    self.logger.info(
                        "Failed auth with {}".format(self.ctx.module))
                    # TODO: Should we render and return a response here?
                    raise self.ctx.module.error

                if not self.check_account(self.account):
                    self.logger.debug(
                        "Authenticated account not valid {}".format(
                            self.ctx.module))
                    # Not authenticated
                    raise self.ctx.module.error

                # done
                self.logger.info(
                    "Successful auth with {}".format(self.ctx.module))
                # TODO: Does this belong here?
                self.db.set_change_by(self.account.entity_id)
                return

    def require(auth_obj, *auth_args, **auth_kw):  # noqa: N805
        """Wrap Flask view functions to require authentication.

        Whenever the view function is called, :meth:`.authenticate` will be
        called.  The result of that call will conditionally call the
        view-function:

          1. If we get a challenge/access denied response from authenticate,
             we simply return that error response.

          2. If no challenge is returned, and we are NOT authenticated after
             calling authenticate, the we return an access-denied response.

          3. If we ARE authenticated after calling authenticate, the
             view-function is called, and its return value returned.

        :param list auth_args:
            Positional arguments for the authenticate call.

        :param dict auth_kw:
            Keyword arguments for the authenticate call.

        :return function:
            Returns a wrapped function.
        """
        def wrap(function):
            @wraps(function)
            def wrapped(*args, **kwargs):
                if auth_obj.ctx.module is None:
                    auth_obj.authenticate(*auth_args, **auth_kw)
                if auth_obj.authenticated:
                    # TODO: Check additional requirements from auth_args
                    # TODO: Should we have some sort of plugin system here?
                    return function(*args, **kwargs)
                # not authenticated.
                if auth_obj.ctx.module.challenge is not None:
                    raise auth_obj.ctx.module.challenge
                raise auth_obj.ctx.module.error
            return wrapped
        return wrap

    @property
    def authenticated(self):
        """Check if the current request has been authenticated."""
        return self.ctx.authenticated

    @lazy_property
    def username(self):
        """Get the currently authenticated user."""
        return self.ctx.username

    @lazy_property
    def account(self):
        return self.ctx.get_account(self.db)

    def clear(self, exception):
        """ Clear auth data. """
        del self.ctx
        del self.username
        del self.account


def build_error(exc_type, message, **custom):
    """ Build an HTTP exception with custom data. """
    custom['message'] = message
    exc = exc_type(message)
    exc.data = custom
    return exc


@python_2_unicode_compatible
class AuthModule(object):
    """Abstract auth module."""

    def __init__(self, app=None, db=None):
        """Initialize module."""
        self.app = app
        self.db = db
        self.user = None

    def detect(self):
        """Detect if auth data was provided."""
        raise NotImplementedError("Not implemented")

    def is_authenticated(self):
        return self.user is not None

    def get_username(self):
        if not self.is_authenticated():
            raise Exception("Not authenticated")
        return self.user

    def do_authenticate(self):
        """Perform authentication."""
        raise NotImplementedError("Not implemented")

    @property
    def challenge(self):
        """ A challenge error response, if available. """
        return None

    @property
    def error(self):
        """An appropriate access denied/auth error response."""
        return Forbidden("")

    def __str__(self):
        return "<{} as {!r}>".format(type(self).__name__, self.user)


class BasicAuth(AuthModule):
    """ HTTP Basic Auth.

    Parses basic auth headers and verifies username and password against
    Cerebrum user accounts.

    Example ``AUTH`` configuration entry:
    ::

        {
            'name': 'BasicAuth',
            'realm': 'foo',
            'whitelist': ['foo', 'bar', ]
        }

    """

    def __init__(self, realm=None, whitelist=None, **kwargs):
        """ Set up basic auth.

        :param str realm:
            The realm to respond with in HTTP 401 challenges (default: None, no
            realm)

        :param list whitelist:
            An optional list of usernames that are allowed to log in using
            basic auth (default: ``None``, everyone allowed)
        """

        super(BasicAuth, self).__init__(**kwargs)
        self.realm = realm
        self.whitelist = whitelist

    def check(self, username, password):
        """Verify username and password."""
        account = Factory.get('Account')(self.db.connection)
        try:
            account.find_by_name(username)
            return account.verify_auth(password)
        except Errors.NotFoundError:
            return False

    def detect(self):
        """Detect Basic-Auth headers."""
        return 'Basic ' in request.headers.get('Authorization', '')

    def do_authenticate(self):
        """Perform auth."""
        auth = request.authorization
        if self.whitelist is not None:
            if auth.username not in self.whitelist:
                self.user = None
                return self.is_authenticated()
        if self.check(auth.username, auth.password):
            self.user = auth.username
        else:
            self.user = None
        return self.is_authenticated()

    @property
    def challenge(self):
        if self.detect():
            return None
        message = "Missing credentials"
        data = {'basic-realm': self.realm, }
        exc = build_error(Unauthorized, message, **data)
        exc.realm = self.realm
        return exc

    @property
    def error(self):
        message = "Invalid credentials"
        data = {'basic-realm': self.realm, }
        return build_error(Forbidden, message, **data)


class SslProxyAuth(AuthModule):
    """ Client certificate authentication.

    NOTE: This requires that the request comes from a SSL-terminated proxy, and
    that the proxy adds headers:

      - X-Ssl-Cert-Verified: (SUCCESS|)
      - X-Ssl-Cert-Fingerprint: <fingerprint>

    The proxy also needs to prevent a client from sending the same headers.

    Example ``AUTH`` configuration entry:
    ::

        {
            'name': 'SslProxyAuth',
            'verified_header': 'X-Ssl-Cert-Verified',
            'verified_value': 'SUCCESS',
            'fingerprint_header': 'X-Ssl-Cert-Fingerprint',
            'certs': {
                '5dd915c1584ce9f30cd2f867365603eac35d68b0': 'foo',
                ...
            },
        }
    """

    def __init__(self,
                 fingerprint_header='X-Ssl-Cert-Fingerprint',
                 verified_header='X-Ssl-Cert-Verified',
                 verified_value='SUCCESS',
                 certs=None,
                 **kwargs):
        """ Set up SSL fingerprint authentication.

        To pass validation, a request must have the ``verified_header`` header,
        and the header value must be ``verified_value``.  In addition, the
        request must have the ``fingerprint_header`` and the value must be
        mapped to a username in ``certs``.

        :param str fingerprint_header:
            Name of a header to look for the SSL fingerprint in. Default is
            'X-Ssl-Cert-Fingerprint'.
        :param str verified_header:
            Name of a header to look for the SSL validation result in. Default
            is 'X-Ssl-Cert-Verified'.
        :param str verified_value:
            Required value of the ``verified_header`` header. Default is
            'SUCCESS'.
        :param dict certs:
            A dictionary-like object that maps fingerprints to usernames.
        """
        super(SslProxyAuth, self).__init__(**kwargs)
        if fingerprint_header:
            self.header_fingerprint_name = fingerprint_header
        else:
            raise ValueError("Empty fingerprint header value")
        if verified_header:
            self.header_verified_name = verified_header
        else:
            raise ValueError("Empty verified header value")
        if verified_value:
            self.header_verified_value = verified_value
        else:
            raise ValueError("Empty verified value")
        self.certs = certs or dict()

    def detect(self):
        """Detect verified client certificate."""
        return self.header_verified_name in request.headers

    def do_authenticate(self):
        if self.header_verified_value != request.headers.get(
                self.header_verified_name):
            # client key failed proxy ca-check
            return False
        fingerprint = request.headers.get(self.header_fingerprint_name)
        self.user = self.certs.get(fingerprint)
        return self.is_authenticated()

    @property
    def challenge(self):
        """ 401 error with SSL hint. """
        if self.detect():
            return None
        message = "Unsigned request, please use valid client certificate"
        return build_error(Unauthorized, message)

    @property
    def error(self):
        """ 403 error. """
        message = "Invalid SSL certificate or signature in request"
        return build_error(Forbidden, message)


class HeaderAuth(AuthModule):
    """ Pass authentication if header contains a given value.

    To pass validation, a request must have the ``header`` header,
    and the header value must be present in the ``keys`` mapping, and map to an
    existing username.

    This is typically used in dev or test environments.

    Example ``AUTH`` configuration entry:
    ::

        {
            'name': 'HeaderAuth',
            'header': 'X-Auth-Key',  # default value, optional
            'keys': {
                "06c48667-f1e6-4bd5-87b3-76b210e88bb0": "foo",
                ...
            },
        }

    """

    def __init__(self, header='X-Auth-Key', keys=None, **kwargs):
        """ Set up API key authentication.

        :param str header:
            Which header to look for API keys in. Default is 'X-Auth-Key'.

        :param dict keys:
            A mapping of header values to usernames.
        """
        super(HeaderAuth, self).__init__(**kwargs)
        self.header = header
        self.keys = keys or dict()

    def detect(self):
        """Detect if header is present."""
        return self.header and self.header in request.headers

    def do_authenticate(self):
        """Verify key and map to user."""
        v = request.headers.get(self.header)
        if not v or v not in self.keys:
            self.user = None
        else:
            self.user = self.keys.get(v)
        return self.is_authenticated()

    @property
    def challenge(self):
        """ 401 error. """
        if self.detect():
            return None
        message = "Missing API key in header"
        data = {'api-key-header': self.header, }
        return build_error(Forbidden, message, **data)

    @property
    def error(self):
        """ 403 error. """
        message = "Invalid API key in header"
        data = {'api-key-header': self.header, }
        return build_error(Forbidden, message, **data)


class ApiSubscriptionAuth(AuthModule):
    """
    Pass authentication if header contains a whitelisted api identifier.

    To pass validation, the configured ``header`` must be present, and its
    value must be registered to an account using the
    :mod:`Cerebrum.modules.apikeys` module.

    Example ``AUTH`` configuration entry:
    ::

        {
            'name': 'ApiSubscriptionAuth',
            'header': 'X-Api-Subscription',
        }
    """

    def __init__(self, header='X-Api-Subscription', **kwargs):
        """
        Set up API key authentication.

        :param str header:
            Which header to look for API keys in. Default is
            'X-Api-Subscription'.
        """
        super(ApiSubscriptionAuth, self).__init__(**kwargs)
        self.header = header

    def detect(self):
        """Detect if header is present."""
        return self.header and self.header in request.headers

    def _map_identifier(self, key):
        """Map api key to username."""
        if not key:
            logger.debug('got empty subscription value')
            return None

        keys = ApiMapping(self.db.connection)
        account = Factory.get('Account')(self.db.connection)

        try:
            mapping = keys.get(key)
            logger.debug('got subscription for account_id=%r (%r)',
                         mapping['account_id'], key)
        except Errors.NotFoundError:
            logger.debug('got non-whitelisted subscription %r', key)
            return None
        except Exception as e:
            logger.debug('got invalid subscription %r: %s',
                         key, str(e))
            return None

        account.find(mapping['account_id'])
        return account.account_name

    def do_authenticate(self):
        v = request.headers.get(self.header)
        self.user = self._map_identifier(v)
        return self.is_authenticated()

    @property
    def challenge(self):
        """ 401 error. """
        message = "Missing API subscription identifier header"
        data = {'api-id-header': self.header, }
        return build_error(Forbidden, message, **data)

    @property
    def error(self):
        """ 403 error. """
        message = "Invalid API subscription identifier"
        data = {'api-id-header': self.header, }
        return build_error(Forbidden, message, **data)


class BasicProxyAuth(BasicAuth):
    """
    HTTP Basic Auth method with hard-coded username and password.

    This auth module should only be used for debugging, or for authenticating a
    proxy using :py:class:`ProxyAuth`.
    """

    def __init__(self, username=None, password=None, **kwargs):
        kwargs['whitelist'] = [username]
        super(BasicProxyAuth, self).__init__(**kwargs)
        self.username = username
        self.password = password

    def check(self, username, password):
        """Verify username and password."""
        return (
            self.username and self.username == username and
            self.password and self.password == password)


class ProxyAuth(object):
    """
    Authentication middleware for proxies.

    This authentication method should be used *in addition* to the regular
    :class:`Authentication` middleware.  It should be used to authenticate a
    proxy before trusting headers provided by it.

    Configuration:
    ::

        PROXY_AUTH = {
            'enable': True,
            'username': 'gateway',
            'realm': 'proxy',
        }
    """

    ctx = AuthContext('ProxyAuth')

    def init_app(self, app, db_ctx):
        self.app = app
        self.db = db_ctx

        config = app.config.setdefault('PROXY_AUTH', {})
        enable = config.setdefault('enable', False)
        self._require_username = config.setdefault('username', 'gateway')
        self._require_password = None
        self._realm = config.setdefault('realm', 'proxy')

        if enable:
            self._require_password = read_password(self._require_username,
                                                   self._realm)
            app.before_request(self.authenticate)
            app.teardown_appcontext(self.clear)

    def authenticate(self, *auth_args, **auth_kwargs):
        """
        Authenticate proxy
        """
        self.ctx.module = BasicProxyAuth(
            app=self.app,
            db=self.db,
            username=self._require_username,
            password=self._require_password,
            realm=self._realm)
        if self.ctx.module.detect():
            logger.debug("Attempting proxy auth with %s", str(self.ctx.module))
            if not self.ctx.module.do_authenticate():
                # This should never happen (invalid proxy configuration)
                logger.error("Failed proxy auth with %s", str(self.ctx.module))
                raise self.ctx.module.error
            logger.info("Successful proxy auth with %s", str(self.ctx.module))
            return
        else:
            # This should never happen (invalid proxy configuration)
            logger.error("Missing proxy auth for %s", str(self.ctx.module))
            raise self.ctx.module.challenge

    @property
    def authenticated(self):
        """Check if the current request has been authenticated."""
        return self.ctx.authenticated

    @lazy_property
    def username(self):
        """Get the currently authenticated user."""
        return self.ctx.username

    def clear(self, exception):
        """ Clear auth data. """
        del self.ctx
        del self.username
