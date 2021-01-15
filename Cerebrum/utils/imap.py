# -*- coding: utf-8 -*-
#
# Copyright 2020 University of Oslo, Norway
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
IMAP-related utilities.


History
-------
py:class:`Imap4SslVersionMixin`
    Originally moved from ``Cerebrum.Utils.CerebrumIMAP4_SSL``.  The old
    version can be seen in:

    Commit: 7ddda8566b45b576ef0e3c288c00a9fed5b215bc
    Date:   Wed Dec 16 11:51:09 2020 +0100
"""
import imaplib
import socket
import ssl


class Imap4SslVersionMixin(imaplib.IMAP4_SSL):
    """
    A changed version of imaplib.IMAP4_SSL that lets the caller specify
    ssl_version in order to please older versions of OpenSSL. CRB-1246
    """
    def __init__(self,
                 host='',
                 port=imaplib.IMAP4_SSL_PORT,
                 keyfile=None,
                 certfile=None,
                 ssl_version=ssl.PROTOCOL_TLSv1):
        """
        """
        self.keyfile = keyfile
        self.certfile = certfile
        self.ssl_version = ssl_version
        imaplib.IMAP4.__init__(self, host, port)

    def open(self, host='', port=imaplib.IMAP4_SSL_PORT):
        """
        """
        self.host = host
        self.port = port
        self.sock = socket.create_connection((host, port))
        # "If not specified, the default is PROTOCOL_SSLv23;...
        # Which connections succeed will vary depending on the version
        # of OpenSSL. For example, before OpenSSL 1.0.0, an SSLv23
        # client would always attempt SSLv2 connections."
        self.sslobj = ssl.wrap_socket(self.sock,
                                      self.keyfile,
                                      self.certfile,
                                      ssl_version=self.ssl_version)
        self.file = self.sslobj.makefile('rb')
