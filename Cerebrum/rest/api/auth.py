#!/usr/bin/env python
# encoding: utf-8
u"""Authentication framework for flask."""

import sys
from flask import request, Response

from Cerebrum import Errors
from Cerebrum.Utils import Factory


class Authentication(object):
    u"""Authentication API"""

    def __init__(self):
        self._modules = list()
        self._module = None  # TODO: Could we link the _module to the request?
        self.challenge = AuthModule.challenge

    def init_app(self, app, db):
        self.app = app
        self.logger = self.app.logger
        self.db = db

        for options in app.config.get('AUTH', []):
            self.add_module(**options)

    def add_module(self, name, *mod_args, **mod_kw):
        u"""Add an authentication module.

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

    def load_module(self, name):
        u"""TODO: Implement proper module loading / dynamic import."""
        if hasattr(sys.modules[__name__], name):
            return getattr(sys.modules[__name__], name)
        raise Exception(u"Unknown authentication module " + name)

    def authenticate(self, *auth_args, **auth_kwargs):
        u"""Perform authentication using the correct request."""
        # TODO: Setup args/kwargs could be used to e.g. restrict allowed
        # authentication backends for a specific call?
        self._module = None
        for module, mod_args, mod_kw in self._modules:
            challenge = mod_kw.pop('challenge', False)
            m = module(app=self.app, db=self.db, *mod_args, **mod_kw)
            if challenge and hasattr(m, 'challenge'):
                self.challenge = m.challenge
            if m.detect():
                self.logger.debug(u"Attempting auth with {}".format(m))
                if m.do_authenticate():
                    self._module = m
                    self.logger.debug(u"Successful auth with {}".format(m))
                    break
                else:
                    self.logger.debug(u"Failed auth with {}".format(m))
                    return m.error(u"Not authenticated")
        if not self.has_auth:
            self.logger.debug(
                u"No auth found with {!r}".format(
                    [x[0] for x in self._modules]))
            self.logger.debug(u"Issuing challenge with {}".format(
                self._challenge))
            return self.challenge

    def require(auth_obj, *auth_args, **auth_kw):
        u"""Wrap flask routes to require authentication.

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
            def wrapped(*args, **kwargs):
                resp = auth_obj.authenticate(*auth_args, **auth_kw)
                if resp:
                    return resp
                if not auth_obj.has_auth:
                    raise Exception(u"Not authenticated")
                # TODO: Should we have an authz map, and look up authorization
                # here?
                return function(*args, **kwargs)
            return wrapped
        return wrap

    @property
    def user(self):
        u"""Get the currently authenticated user."""
        if self.has_auth:
            return self._module.get_user()
        raise Exception(u"Not authenticated")

    @property
    def has_auth(self):
        u"""Check if the current request has been authenticated."""
        if not self._module:
            return False
        return self._module.is_authenticated()

    @property
    def challenge(self):
        u"""Return a challenge response."""
        if callable(self._challenge):
            return self._challenge()
        return self._challenge

    @challenge.setter
    def challenge(self, challenge):
        u"""Set the challenge."""
        assert callable(challenge) or isinstance(challenge, Response)
        self._challenge = challenge


class AuthModule(object):
    u"""Abstract auth module."""

    def __init__(self, app=None, db=None, *args, **kwargs):
        u"""Initialize module."""
        self.app = app
        self.db = db
        self.logger = self.app.logger
        self.user = None

    def detect(self):
        u"""Detect if auth data was provided."""
        raise NotImplementedError(u"Not implemented")

    def is_authenticated(self):
        return self.user is not None

    def get_user(self):
        if not self.is_authenticated():
            raise Exception(u"Not authenticated")
        return self.user

    def do_authenticate(self):
        u"""Perform authentication."""
        raise NotImplementedError(u"Not implemented")

    @staticmethod
    def challenge(msg=u""):
        u"""An appropriate response to indicate that auth is wanted."""
        return Response(msg, 401)

    @staticmethod
    def error(msg=u""):
        u"""An appropriate acces denied/auth error response."""
        return Response(msg, 403)


class BasicAuth(AuthModule):
    u"""HTTP-Basic-Auth"""

    def __init__(self, realm, whitelist=None, app=None, db=None):
        super(BasicAuth, self).__init__(app=app, db=db)
        self.realm = realm
        self.whitelist = whitelist

    def check(self, username, password):
        u"""Verify username and password."""
        account = Factory.get('Account')(self.db.connection)
        try:
            account.find_by_name(username)
            return account.verify_auth(password)
        except Errors.NotFoundError:
            return False

    def detect(self):
        u"""Detect Basic-Auth headers."""
        return 'Basic ' in request.headers.get('Authorization', '')

    def do_authenticate(self):
        """Perform auth."""
        auth = request.authorization
        if self.whitelist is not None:
            if auth.username not in self.whitelist:
                self.user = None
                self.logger.debug(
                    "BasicAuth: {} not in whitelist".format(auth.username))
                return self.is_authenticated()
        if self.check(auth.username, auth.password):
            self.logger.info("BasicAuth: Valid credentials for {!r}".format(
                auth.username))
            self.user = auth.username
        else:
            self.logger.info("BasicAuth: Invalid credentials for {!r}".format(
                auth.username))
            self.user = None
        return self.is_authenticated()

    def challenge(self, msg=u"Log in"):
        u"""An appropriate response to indicate that Basic-Auth is wanted."""
        return Response(
            msg, 401,
            {'WWW-Authenticate': 'Basic realm="{}"'.format(self.realm)})

    def error(self, msg=u"Invalid credentials"):
        u"""Respond with 401 Unauthorized in case of invalid credentials."""
        return self.challenge(msg)


class CertAuth(AuthModule):
    u"""Client certificate authentication"""

    def __init__(self, certs, app=None, db=None):
        super(CertAuth, self).__init__(app=app, db=db)
        self.certs = certs

    def detect(self):
        u"""Detect verified client certificate."""
        return request.headers.get('X-Ssl-Cert-Verified') == 'SUCCESS'

    def do_authenticate(self):
        fingerprint = request.headers.get('X-Ssl-Cert-Fingerprint')
        self.user = self.certs.get(fingerprint)
        if self.user:
            self.logger.info(
                "CertAuth: Authenticated user {} with certificate {}".format(
                    self.user, fingerprint))
        return self.is_authenticated()


class HeaderAuth(AuthModule):
    u"""Pass authentication if header contains a constant."""

    def __init__(self, header, values, app=None, db=None):
        super(HeaderAuth, self).__init__(app=app, db=db)
        self.header = header
        self.values = values

    def detect(self):
        return bool(request.headers.get(self.header))

    def do_authenticate(self):
        # TODO: What is the best way to convey info to the Auth modules?
        v = request.headers.get(self.header)
        if not v or v not in self.values:
            self.user = None
        else:
            self.user = v
        return self.is_authenticated()
