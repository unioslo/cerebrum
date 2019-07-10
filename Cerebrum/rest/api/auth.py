#!/usr/bin/env python
# coding: utf-8
#
# Copyright 2016-2019 University of Oslo, Norway
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
""" Authentication context for a flask app."""
from __future__ import unicode_literals

import logging
import sys
from functools import wraps

from flask import request, g
from mx import DateTime
from six import python_2_unicode_compatible
from werkzeug.exceptions import Forbidden
from werkzeug.exceptions import Unauthorized as _Unauthorized

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.apikeys.dbal import ApiKeys
from Cerebrum.utils.descriptors import lazy_property

logger = logging.getLogger(__name__)


class AuthContext(object):
    """ Auth context.

    This is a descriptor and proxy object for the currently used AuthModule.

    >>> from flask import Flask
    >>> app = Flask('doctest')
    >>> class Auth(object):
    ...     ctx = AuthContext()
    >>> auth = Auth()

    >>> with app.app_context():
    ...     isinstance(auth.ctx, AuthContext)
    True

    >>> with app.app_context():
    ...     auth.ctx.module == None
    True

    >>> with app.app_context():
    ...     auth.ctx.module = AuthModule()
    ...     isinstance(auth.ctx.module, AuthModule)
    True
    """

    OP_CLS = Factory.get(b'Account')

    def __get__(self, obj, cls=None):
        if getattr(g, '_auth_ctx', None) is None:
            setattr(g, '_auth_ctx', AuthContext())
        return getattr(g, '_auth_ctx')

    def __delete__(self, obj):
        if hasattr(g, '_auth_ctx'):
            delattr(g, '_auth_ctx')

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
        """ true if current request is authenticated. """
        if self._module is None:
            return False
        return self._module.is_authenticated()

    @property
    def username(self):
        """ the authenticated username, if avaliable. """
        if self.authenticated:
            return self.module.get_username()
        return None

    def get_account(self, db_ctx):
        """ the authenticated user, if available. """
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
    """ Authentication middleware. """

    ctx = AuthContext()

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
            The module name (TODO: Implement proper loading)

        :param bool challenge:
            If True, use this module to produce a challenge response, if no
            authentication information is given with the request.  (default:
            False)

        :param *list mod_args:
            Positional arguments for the module.

        :param **dict mod_kw:
            Keyword arguments for the module.
        """
        module = self.load_module(name)
        # TODO: Implement auth module priority:
        #       - which module to try first, which to try last?
        #       - which module to use for challenge, when multiple?
        self._modules.append(tuple((module, mod_args, mod_kw)))

    @staticmethod
    def load_module(name):
        """TODO: Implement proper module loading / dynamic import."""
        if hasattr(sys.modules[__name__], name):
            return getattr(sys.modules[__name__], name)
        raise Exception("Unknown authentication module " + name)

    def check_account(self, account):
        """ Check if account is OK. """
        if account is None:
            return False
        if account.expire_date and account.expire_date < DateTime.now():
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
        """Wrap flask routes to require authentication.

        When called, authenticate will be called with the given arguments, and:
          1. If a challenge/access denied response is returned by authenticate,
             the function will return that response.
          2. If no challenge is returned, and we are NOT authenticated after
             calling authenticate, an exception is raised.
          3. If we ARE authenticated after calling `authenticate', the function
             is called, and its return value returned.

        :param *list auth_args:
            Positional arguments for the `authenticate` call.

        :param **dict auth_kw:
            Keyword arguments for the `authenticate` call.

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
        """ clear auth data. """
        del self.ctx
        del self.username
        del self.account


def build_error(exc_type, message, **custom):
    """ Build an HTTP exception with data.  """
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
        """ A challenge error response, if avaliable. """
        return None

    @property
    def error(self):
        """An appropriate access denied/auth error response."""
        return Forbidden("")

    def __str__(self):
        return "<{} as {!r}>".format(type(self).__name__, self.user)


class BasicAuth(AuthModule):
    """ HTTP Basic Auth

    Parses basic-auth parameters and validates username and password with users
    in Cerebrum.

    Configuration:

        {
            'name': 'BasicAuth',
            'realm': 'foo',
            'whitelist': ['foo', 'bar', ]
        },

    """

    def __init__(self, realm=None, whitelist=None, **kwargs):
        """ Set up basic auth

        :param str realm:
            The realm to respond with in HTTP 401 challenges (default: None, no
            realm)
        :param list whitelist:
            A list of usernames allowed to log in using basic auth (default:
            None, everyone allowed)
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

      - X-Ssl-Cert-Verfied: (SUCCESS|)
      - X-Ssl-Cert-Fingerprint: <fingerprint>

    The proxy also needs to prevent a client from sending the same headers.

    Configuration:

        {
            'name': 'SslProxyAuth',
            'verified_header': 'X-Ssl-Cert-Verfied',
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

        To pass validation, a request must have the `verified_header` header,
        and the header value must be `verified_value`. In addition, the
        request must have the `fingerprint_header` and the value must be
        mapped to a username in `certs`.

        :param str fingerprint_header:
            Name of a header to look for the SSL fingerprint in. Default is
            'X-Ssl-Cert-Fingerprint'.
        :param str verified_header:
            Name of a header to look for the SSL validation result in. Default
            is 'X-Ssl-Cert-Verified'.
        :param str fingerprint_header:
            Required value of the `verified_header` header. Default is
            'SUCCESS'.
        :param str fingerprint_header:
            Which header to look for SSL fingerprint in. Default is
            'X-Ssl-Cert-Fingerprint'.
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

    Configuration:

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
            A dictionary-like object that maps keys to usernames.
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
        if not v or v not in self.keys.keys():
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


class ApiKeyAuth(HeaderAuth):
    """
    Pass authentication if header contains a whitelisted api key.

    Api key whitelist is implemented by Cerebrum.modules.apikeys.

    Configuration:

        {
            'name': 'ApiKeyAuth',
            'header': 'X-Auth-Key',  # default value, optional
        }
    """

    def __init__(self, **kwargs):
        """
        Set up API key authentication.

        :param str header:
            Which header to look for API keys in. Default is 'X-Auth-Key'.
        """
        if 'keys' in kwargs:
            raise TypeError("__init__() got an unexpected keyword "
                            "argument 'keys'")
        super(ApiKeyAuth, self).__init__(**kwargs)

    def _check_apikey(self, key):
        """Map api key to username."""
        if not key:
            logger.debug('ApiKeyAuth got empty key value')
            return None

        keys = ApiKeys(self.db.connection)
        account = Factory.get('Account')(self.db.connection)

        try:
            account_id, label = keys.map(key)
            logger.debug('ApiKeyAuth got key for account_id=%r, label=%r',
                         account_id, label)
        except Errors.NotFoundError:
            logger.debug('ApiKeyAuth got non-whitelisted key')
            return None
        except Exception as e:
            logger.debug('ApiKeyAuth got invalid key: %s',
                         str(e))
            return None

        account.find(account_id)
        return account.account_name

    def do_authenticate(self):
        v = request.headers.get(self.header)
        self.user = self._check_apikey(v)
        return self.is_authenticated()
