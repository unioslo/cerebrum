# -*- coding: utf-8 -*-
# Copyright 2014-2017 University of Oslo, Norway
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
""" This module contains subclasses of httplib and urllib2 with support for:
    - Require and validate server-side certificates
    - Verify hostname against certificate

Note that the classes in this module makes assubmtions on how the parent
classes (from httplib and urrlib2) works internally. When we go for a newer
version of python, this must be taken into account. """


import httplib
import operator
import os.path
import socket
import ssl
import urllib2

from backports import ssl_match_hostname
from collections import OrderedDict
from warnings import warn


SSLError = ssl.SSLError
""" Import SSLError directly from https"""


# SSL version map, sorted by value
SSL_VERSION = OrderedDict(
    sorted(
        ((attr[len('PROTOCOL_'):], getattr(ssl, attr))
         for attr in dir(ssl)
         if attr.startswith('PROTOCOL_')),
        key=operator.itemgetter(1)))


# FIXME: Should probably default to list(SSL_VERSION.keys())[-1]
DEFAULT_SSL_VERSION = 'TLSv1'


class SSLConfig(object):

    """ Configuration object for SSL parameters.

    This is an object used to control the behaviour of the HTTPSConnection
    class in this module.

    Typical use:

      conf = SSLConfig()
      conn = HTTPSConnection('localhost', 80, ssl_config=conf)

    If you need pass off the type to another class that does the init call,
    you'll need to build a configured HTTPSConnection class. This is needed
    with urllib2, for example:

      cls = HTTPSConnection.configure(conf)
      handler = HTTPSHandler(ssl_connection=cls)
      opener = urllib2.build_opener(handler)

    """
    # Certificate requirement and validation settings.
    # See the ssl module documentation for more info.
    NONE = ssl.CERT_NONE
    OPTIONAL = ssl.CERT_OPTIONAL
    REQUIRED = ssl.CERT_REQUIRED

    def __init__(self, ca_certs=None, certfile=None, keyfile=None):
        """ Create a new configuration object.

        Initializes a new settings object, with healthy defaults.

        :param str ca_certs: see set_ca_chain
        :param str certfile: see set_cert
        :param str keyfile: see set_cert

        """
        self._wrap_param = dict()

        if ca_certs is not None:
            self.set_ca_chain(ca_certs)

        # Note: This will not work unless a ca_certs file is provided, or
        # set_ca_validate is set to something else later.
        self.set_ca_validate(SSLConfig.REQUIRED)

        if certfile is not None:
            self.set_cert(certfile, keyfile)

        self.set_verify_hostname(True)
        self.set_ssl_version(DEFAULT_SSL_VERSION)

    def set_ca_chain(self, ca_certs):
        """ Set the peer certificate.

        :param str ca_certs: The path to a file that contains CA certificates.
            This parameter is used as 'ca_certs' in the ssl.wrap_socket call.

        """
        if not os.path.exists(ca_certs):
            raise ValueError("No CA file '%s'" % ca_certs)
        self._wrap_param['ca_certs'] = ca_certs

    def set_ca_validate(self, req):
        """ If peer certificates should be validated.

        :param str req: The validate requirement, must be one of the constants:
            'REQUIRE', 'OPTIONAL', 'NONE'. This decides if certificates should
            be checked against a CA certificate. See the documentation for the
            ssl module for more info.

        """
        if req not in (SSLConfig.NONE, SSLConfig.OPTIONAL, SSLConfig.REQUIRED):
            raise ValueError("Invalid validate setting '%s'" % req)
        self._wrap_param['cert_reqs'] = req

    def set_cert(self, certfile, keyfile=None, password=None):
        """ Set certificate.

        :param str certfile: Path to a certificate file in PEM format. If the
            certificate contains a key, there's no need to set keyfile
            separately. This parameter is used as 'certfile' in the
            ssl.wrap_socket call.
        :param str keyfile: Path to a private key file in PEM format. If the
            certfile does not contain a private key, this settings is required.
            This parameter is used as 'certfile' in the ssl.wrap_socket call.
        :param str password: A password that decrypts the private key, if
            required. Currently unsupported.

        Note: If the private key requires a password, but none is given, the
        user will be prompted for a password each time a connection is
        attempted.

        """
        if password is not None:
            # We'll need pyOpenSSL.Context or something else that can provide
            # libOpenSSL with a callback to fetch the password to support this.
            # The default behaviour of libOpenSSL is to cause an input read
            # where the user is expected to type the password.
            raise NotImplementedError(
                'The password argument is not supported')

        if certfile is None and keyfile is not None:
            raise ValueError('Cannot specify keyfile without certfile')

        for ftype, path in (('certificate', certfile),
                            ('private key', keyfile)):
            if path is not None and not os.path.exists(path):
                raise ValueError("No %s file '%s'" % (ftype, path))
        self._wrap_param['certfile'] = certfile
        self._wrap_param['keyfile'] = keyfile

    def set_ssl_version(self, ssl_version):
        """ Set the minimum ssl protocol version to accept.

        :param str ssl_version: The version to accept. Must be one of
            the keys in `SSL_VERSION`.  This affects the selection of ssl
            protocols that are reported when attempting to set up the ssl
            connection. See the documentation for the ssl module for more info.

        """
        # Legacy support: If given a constant (int), look up the name:
        for k, v in SSL_VERSION.items():
            if ssl_version == v:
                ssl_version = k

        if ssl_version not in SSL_VERSION:
            raise ValueError('Invalid SSL version %r' % ssl_version)
        self._wrap_param['ssl_version'] = SSL_VERSION[ssl_version]

    def set_verify_hostname(self, do_verify):
        """ Enable or disable hostname validation.

        If enabled, a ssl_match_hostname.CertificateError is raised if the
        certificate is not valid for the hostname we connected to. If disabled,
        invalid hostnames will only cause a RuntimeWarning.

        :param bool do_verify: True if certificate must be valid for the
            hostname. If False, an invalid hostname will only cause a warning.

        """
        self._do_verify_hostname = do_verify

    def verify_hostname(self, sock, hostname):
        """ Attempt to match the peer hostname and certificate.

        If a certificate was not provided, and we don't require a certificate,
        this function will report a warning if the hostname doesn't match. This
        is also true if we disable hostname verification with
        set_verify_hostname(False). If we require peer certificates and
        hostname verification, this function will raise a
        ssl_match_hostname.CertificateError if the hostname doesn't match.

        :param ssl.SSLSocket sock: The connected socket we want to verify
        :param string hostname: The hostname that should match the certificate

        """
        cert = sock.getpeercert()

        if cert is None:
            warn(RuntimeWarning('Peer did not supply a certificate.'))

        if not cert and self._wrap_param['cert_reqs'] == SSLConfig.NONE:
            # Empty dict or None, don't care. We don't even look at the
            # certificate.
            return

        if cert is None and self._wrap_param['cert_reqs'] == SSLConfig.OPTIONAL:
            # It's ok that the peer did not provide a certificate,
            # and without a certificate there's nothing to verify.
            #
            # We should NOT get an empty dict here!
            return

        try:
            ssl_match_hostname.match_hostname(cert, hostname)
        except ssl_match_hostname.CertificateError:
            if not self._do_verify_hostname:
                # We checked it anyway
                warn(RuntimeWarning('Invalid hostname in certificate'))
                return
            raise

    def wrap_socket(self, sock, server=False):
        """ Wrap socket with SSLSocket, with the provided settings.

        Calls ssl.wrap_socket with ssl parameters from this object.

        :param sock: The socket
        :param server: True if this is a listening socket.

        """
        # Warn about bad decision making:
        if not (server or
                self._wrap_param.get('cert_reqs', None) == SSLConfig.REQUIRED):
            warn(RuntimeWarning('Peer certificate not required'))
        if not (server or self._do_verify_hostname):
            warn(RuntimeWarning('Certificate hostname validation disabled'))

        params = self._wrap_param.copy()
        params['server_side'] = server

        return ssl.wrap_socket(sock, **params)

    def __unicode__(self):
        """ Return a unicode representation of this object. """
        return u'SSLConfig(%s, %s)' % (
            u', '.join(('%s=%s' % (k, v) for k, v in
                       self._wrap_param.iteritems())),
            u'verify_hostname=%s' % self._do_verify_hostname)

    def __str__(self):
        """ Return a string representation of this object. """
        return unicode(self).encode('utf-8')


# Backwards compability:
for const, value in SSL_VERSION.items():
    setattr(SSLConfig, const, value)


class HTTPSConnection(httplib.HTTPSConnection, object):

    """ HTTPSConnection that can validate SSL certificates. """

    ssl_config = None
    """ If we don't have control over the init call, we can set the ssl_config
    as a static attribute on the class. """

    default_timeout = None
    """ I we don't have control over the init call, we can set a default
    timeout here. This is used if the timeout-keyword is not given on init.

    If not set, the socket will fall back to a global default timeout. This can
    be changed with socket.setdefaulttimeout(timeout). The default global
    timeout is None (never times out). """

    def __init__(self, *args, **kwargs):
        """ Initialize the connection

        :param SSLConfig ssl_config: The SSL configuration for this connection.
            Default value is the ssl_config attribute of the class.
        :param float timeout: Timeout of the socket, in seconds. Default: None.

        Note: In addition, this function accepts all arguments that
        HTTPConnection accepts, including mandatory, positional arguments.

        """
        self._ssl_config = kwargs.pop('ssl_config', self.ssl_config)

        # These are the options that HTTPSConnection accepts, that we can also
        # set in the SSLConfig. If they are given to HTTPSConnection, we prefer
        # those over whatever was passed in the config.
        cert = kwargs.get('cert_file')
        key = kwargs.get('key_file')
        if self._ssl_config is not None:
            if cert is not None or key is not None:
                self._ssl_config.set_cert(cert, key)

        super(HTTPSConnection, self).__init__(*args, **kwargs)

    def connect(self):
        """ Create socket and connect. """
        if self._ssl_config is None:
            warn(RuntimeWarning('No SSL configuration given, using default'))
            super(HTTPSConnection, self).connect()
            return

        if not isinstance(self._ssl_config, SSLConfig):
            raise TypeError('ssl_config must be an instance of SSLConfig')

        timeout = socket._GLOBAL_DEFAULT_TIMEOUT
        if self.timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
            timeout = self.timeout
        elif self.default_timeout:
            timeout = self.default_timeout

        sock = socket.create_connection((self.host, self.port), timeout)
        if self._tunnel_host:
            self.sock = sock
            self._tunnel()

        self.sock = self._ssl_config.wrap_socket(sock)
        self._ssl_config.verify_hostname(self.sock, self.host)

    @classmethod
    def configure(cls, ssl_config, timeout=None):
        """ Get a new static version of type cls, with ssl_config set.

        :param type cls: The type we call this function on.
        :param SSLConfig ssl_config: The configuration to use with the class.
        :param int,float,None timeout: Default socket timeout for the
            connection, in seconds. If None, the default, global socket timeout
            will be used in stead. Default: None.

        :return type: A subclass of cls with a static set ssl_config attribute.

        """
        if not isinstance(ssl_config, SSLConfig):
            raise TypeError('ssl_config must be an instance of SSLConfig')
        if not isinstance(timeout, (int, float, type(None))):
            raise TypeError('timeout must be an int, float or None')
        return type('ConfiguredHTTPSConnection',
                    tuple(cls.mro()),
                    dict(ssl_config=ssl_config, default_timeout=timeout))


class HTTPSHandler(urllib2.HTTPSHandler, object):

    """ HTTPSHandler that enables use of any HTTPConnection-like class.

    Note: This class re-raises urllib2.URLError as ssl.SSLError on SSL-related
    failures. """

    def __init__(self, ssl_connection=HTTPSConnection, **kwargs):
        """ Enable override of the ssl connection object.

        :param type ssl_connection: The HTTP(S) connection class to use.
            Default: HTTPSConnection

        For more, see urllib2.HTTPSHandler.

        """
        self.ssl_connection = ssl_connection
        super(HTTPSHandler, self).__init__(**kwargs)

    def https_open(self, req):
        """ See urllib2.HTTPSHandler. """
        try:
            return self.do_open(self.ssl_connection, req)
        except urllib2.URLError, err:
            # I want to throw SSLErrors! This means SSLErrors will start their
            # tracebacks here but all other exceptions should be fine.
            if hasattr(err, 'reason') and isinstance(err.reason, ssl.SSLError):
                raise err.reason
            else:
                raise
