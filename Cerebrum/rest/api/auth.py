#!/usr/bin/env python
# coding: utf-8
#
# Copyright 2016 University of Oslo, Norway
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

import sys
from flask import request, g
from werkzeug.exceptions import Unauthorized as _Unauthorized
from werkzeug.exceptions import Forbidden
from functools import wraps

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.descriptors import lazy_property


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
            ac.find_by_name(self.username)
            return ac
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
        self._modules.append(tuple((module, mod_args, mod_kw)))

    @staticmethod
    def load_module(name):
        """TODO: Implement proper module loading / dynamic import."""
        if hasattr(sys.modules[__name__], name):
            return getattr(sys.modules[__name__], name)
        raise Exception("Unknown authentication module " + name)

    def authenticate(self, *auth_args, **auth_kwargs):
        """ Perform authentication with first matched method.

        If no module succeeds auth, then the last module will be selected as
        active (e.g. for challenge / error).
        """
        for module, mod_args, mod_kw in self._modules:
            self.ctx.module = module(app=self.app, db=self.db,
                                     *mod_args, **mod_kw)
            if self.ctx.module.detect():
                # Need to log auth attempts
                self.logger.info(
                    "Attempting auth with {}".format(type(self.ctx.module)))
                if self.ctx.module.do_authenticate():
                    # Need to log successful login attempts
                    self.logger.info(
                        "Successful auth with {}".format(self.ctx.module))
                    # TODO: Does this belong here?
                    self.db.set_change_by(self.account.entity_id)
                    return
                else:
                    # Need to log failed login attempts
                    self.logger.debug(
                        "Failed auth with {}".format(self.ctx.module))
                    # TODO: Should we render and return a response here?
                    raise self.ctx.module.error

    def require(auth_obj, *auth_args, **auth_kw):
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
    """HTTP-Basic-Auth"""

    def __init__(self, realm=None, whitelist=None, **kwargs):
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
        ch = Unauthorized("Log in")
        ch.realm = self.realm
        return ch

    @property
    def error(self):
        """Respond with 401 Unauthorized in case of invalid credentials."""
        return Forbidden("Invalid credentials")


class SslProxyAuth(AuthModule):
    """ Client certificate authentication.

    NOTE: This requires that the request comes from a SSL-terminated proxy, and
    that the proxy adds headers:

      - X-Ssl-Cert-Verfied: (SUCCESS|)
      - X-Ssl-Cert-Fingerprint: <fingerprint>

    The proxy also needs to prevent the client from sending the same headers.
    """

    def __init__(self, certs=None, **kwargs):
        super(SslProxyAuth, self).__init__(**kwargs)
        self.certs = certs

    def detect(self):
        """Detect verified client certificate."""
        return request.headers.get('X-Ssl-Cert-Verified') == 'SUCCESS'

    def do_authenticate(self):
        fingerprint = request.headers.get('X-Ssl-Cert-Fingerprint')
        self.user = self.certs.get(fingerprint)
        return self.is_authenticated()


class HeaderAuth(AuthModule):
    """Pass authentication if header contains a constant."""

    def __init__(self, header='X-Auth-Key', keys=None, **kwargs):
        super(HeaderAuth, self).__init__(**kwargs)
        self.header = header
        self.keys = keys

    def detect(self):
        """Detect if header is present."""
        return bool(request.headers.get(self.header))

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
        if self.detect():
            return None
        return Unauthorized("No header '{!s}'".format(self.header))
