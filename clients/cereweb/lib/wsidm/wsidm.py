import os
import sys

import cerebrum_path
import cereconf

import Serve_services
import Serve_services_types
from Cerebrum.Utils import Factory

from httplib import HTTPConnection
from M2Crypto import SSL
from Cerebrum.lib.cerews.SignatureHandler import SignatureHandler

log = Factory.get_logger('root')

try:
    from Cerebrum.lib.cerews.dom import DomletteReader as ReaderClass
except ImportError, e:
    log.warn("Could not import DomletteReader.  Install 4Suite for extra performance.")
    from xml.dom import expatbuilder
    class ReaderClass(object):
        fromString = staticmethod(expatbuilder.parseString)
        fromStream = staticmethod(expatbuilder.parse)


class WSIdmHTTPSConnection(HTTPConnection):
    def __init__(self, host, port=443, strict=None):
        HTTPConnection.__init__(self, host, port, strict)
        self.ctx= None
        self.sock= None
        self.ca_path=None
        self.log = Factory.get_logger('root')
        if hasattr(cereconf, "WSIDM_CA_PATH"):
            self.ca_path = cereconf.WSIDM_CA_PATH
        else:
            self.log.error('Missing path to CA certificates.  ' + \
                'Add WSIDM_CA_PATH to cereconf.py.')
            exit(1)
        self.host = host
        if port is None:
            self.port = 443
        if ':' in self.host:
            tab = self.host.split(':')
            self.host = tab[0]
            self.port = int(tab[1])

    def connect(self):
        "Connect to a host on a given (SSL) port."
        self._init_ssl()
        sock = SSL.Connection(self.ctx)
        sock.connect((self.host, self.port))
        self.sock= sock

    def _init_ssl(self):
        ctx = SSL.Context('sslv23')
        ctx.load_verify_info(capath=self.ca_path)
        ## typical options for a client
        ctx.set_options(SSL.op_no_sslv2)
        ctx.set_verify((SSL.verify_fail_if_no_peer_cert|SSL.verify_peer), 9)
        self.ctx= ctx


class WSIdm(object):
    def __init__(self):
        self.wsidm_username = None
        self.wsidm_password = None
        self.wsidm_url = None
        self.log = Factory.get_logger('root')
        if hasattr(cereconf, "WSIDM_USERNAME"):
            self.wsidm_username = cereconf.WSIDM_USERNAME
        else:
            log.error('WSIDM_USERNAME is missing in cereconf.py')
            exit(1)
        if hasattr(cereconf, "WSIDM_PASSWORD"):
            self.wsidm_password = cereconf.WSIDM_PASSWORD
        else:
            self.log.error('WSIDM_PASSWORD is missing in cereconf.py')
            exit(2)
        if hasattr(cereconf, "WSIDM_URL"):
            self.wsidm_url = cereconf.WSIDM_URL
        else:
            self.log.error('WSIDM_URL is missing in cereconf.py')
            exit(3)

        self.zsi_options = {
            'readerclass'   : ReaderClass,
            'transport'     : WSIdmHTTPSConnection,
            }

    def _get_wsidm_port(self, useDigest=False):
        locator = Serve_services.ServeLocator()
        #port = locator.ServeLocator()
        port = locator.getServe(url=self.wsidm_url, **self.zsi_options)
        port.binding.sig_handler = SignatureHandler(self.wsidm_username,
                                                    self.wsidm_password,
                                                    useDigest)
        return port

    def checkIdentity(self, bdate, ssn, studid, pin):
        request = Serve_services.kjerneCheckIdRequest()
        request._birthDate = bdate
        request._ssn = ssn
        request._studentId = studid
        request._pin = pin
        port = self._get_wsidm_port()
        response = port.kjerneCheckId(request)
        ret = None
        if response:
            ret = response._kjerneCheckIdReturn
        return ret
        

