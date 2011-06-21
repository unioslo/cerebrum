#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2010 University of Oslo, Norway
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
This file provides a SOAP server for the Individuation service at UiO.

This is the glue between Cerebrum and twisted's soap server, as most Cerebrum
relevant functionality should be placed in Cerebrum/modules/cis/, which should
not know anything about twisted.

TODO: Describe ...

"""

import sys, socket
import getopt
import SoapListener

import cerebrum_path, cereconf
from Cerebrum.modules.cis import Individuation, IndividuationMessages
from Cerebrum.Utils import Messages, dyn_import
from Cerebrum import Errors

from soaplib.core.service import rpc
from soaplib.core.model.primitive import String, Integer, Boolean
from soaplib.core.model.clazz import ClassModel, Array
from soaplib.core.model.exception import Fault

from twisted.python import log

try:
    from twisted.internet import ssl
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


class Account(ClassModel):
    # FIXME: define namespace properly 
    __namespace__ = 'account'
    uname = String
    priority = Integer
    status = String

class IndividuationServer(SoapListener.BasicSoapServer):
    """
    This class defines the SOAP actions that should be available to
    clients. All those actions are decorated as a rpc, defining
    what parameters the methods accept, types and what is returned.
    """

    # The class where the Cerebrum-specific functionality is done
    individuation = None

    # The hock for the site object
    site = None

    def _get_cache(self, session_id):
        """Get the cache which is stored in the session. A temporary cache is
        created if the session doesn't exist (happens at server restarts)."""
        # Besides, the client could send its previous session id according to
        # what is created by request.getSession() at the same request. This
        # might only happen when the server restarts, so it might not be a real
        # problem.
        try:
            cache = SoapListener.ISessionCache(self.site.getSession(session_id))
        except KeyError:
            # Session doesn't exists, creating default one. Affects only the
            # first call.
            # TODO: This will be fixed when we're able to get hold of the
            # session from the request, and not as a soap-parameter.
            cache = SoapListener.SessionCache()
        if not cache.has_key('msgs'):
            cache['msgs'] = Messages(text=IndividuationMessages.messages)
        return cache

    def call_wrapper(self, call, params):
        """Subclassing the call wrapper to raise Faults instead of Cerebrum
        errors. Also translates the error message for the user."""
        self.cache = self._get_cache(params.session_id)
        try:
            return super(IndividuationServer, self).call_wrapper(call, params)
        except Errors.CerebrumRPCException, e:
            msg = self.cache['msgs'][e.args[0]] % e.args[1:]
            raise Fault(faultstring=e.__doc__ + ': ' + msg)

    @rpc(String, String, _returns=Boolean)
    def set_language(self, language, session_id=None):
        """
        Sets what language feedback messages should be returned in.
        """
        # TODO: improve validation of the language code 
        if language not in ('en', 'no'):
            return False
        self.cache['msgs'].lang = language
        return True

    @rpc(String, String, String, _returns=Array(Account))
    def get_usernames(self, id_type, ext_id, session_id=None):
        """
        Based on id-type and the id, identify a person in Cerebrum and return a
        list of the persons accounts and their status. If person exist but
        doesn't have any accounts an empty list is returned.  If no person match
        the id_type and id an exception is thrown.

        The list is sorted by the person's user priorities, the primary account
        listed first. The types of user status are:

          - *Inactive*: if the account is reserved, deleted or expired, or if it
            has an active quarantine other than autopassord.
          - *PasswordQuarantined*: if the account is not inactive, but has a
            quarantine of type 'autopassord'.
          - *Active*: if the account isn't inactive and hasn't any quarantine.
        """
        ret = []
        # get_person_accounts returns a list of dicts on the form:
        # [{'uname': '...', 'priority': '...', 'status': '...'}, ...]
        for acc in self.individuation.get_person_accounts(id_type, ext_id):
            a = Account()
            for k, v in acc.items():
                setattr(a, k, v)
            ret.append(a)
        return ret

    @rpc(String, String, String, String, String, String, _returns=Boolean)
    def generate_token(self, id_type, ext_id, username, phone_no, browser_token, session_id=None):
        """
        Send a token by SMS to the persons phone and store the token in
        Cerebrum. The input must be matched to only one existing person in
        Cerebrum, including the phone number.
        """
        return self.individuation.generate_token(id_type, ext_id, username,
                                            phone_no, browser_token)

    @rpc(String, String, String, String, _returns=Boolean)
    def check_token(self, username, token, browser_token, session_id=None):
        """
        Check if a given token is correct for the given user.

        Throws an exception if the token is too old, or in case of too many
        failed attempts.
        """
        return self.individuation.check_token(username, token, browser_token)

    @rpc(String, String, _returns=Boolean)
    def abort_token(self, username, session_id=None):
        """
        Remove token for given user from Cerebrum. Used in case the user wants
        to abort the process.
        """
        return self.individuation.delete_token(username)

    @rpc(String, String, String, String, String, _returns=Boolean)
    def set_password(self, username, new_password, token, browser_token,
                     session_id=None):
        """
        Set new password for a user if the tokens are valid and the password is
        good enough.
        """
        return self.individuation.set_password(username, new_password, token, browser_token)

    @rpc(String, String, _returns=Boolean)
    def validate_password(self, password, session_id=None):
        """
        Check if a given password is good enough. Returns either True or throws
        exceptions with an explanation of what is wrong with the password.
        """
        return self.individuation.validate_password(password)

def usage(exitcode=0):
    print """Usage: %s [-p <port number] [-l logfile] [--unencrypted]
  -p | --port num   Run on alternative port (default: ?)
  -l | --logfile:   Where to log
  --instance        The individuation instance which should be used. Defaults
                    to cereconf.INDIVIDUATION_INSTANCE. E.g:
                        Cerebrum.modules.cis.Individuation/Individuation
                    or:
                        Cerebrum.modules.cis.UiAindividuation/Individuation

  --unencrypted     Don't use https
  -h | --help       Show this and quit
    """
    sys.exit(exitcode)


if __name__=='__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'p:l:h',
                                   ['port=', 'unencrypted', 'logfile=',
                                    'help', 'instance='])
    except getopt.GetoptError:
        usage(1)

    use_encryption = CRYPTO_AVAILABLE
    port     = getattr(cereconf, 'INDIVIDUATION_SERVICE_PORT', 0)
    logfile  = getattr(cereconf, 'INDIVIDUATION_SERVICE_LOGFILE', None)
    instance = getattr(cereconf, 'INDIVIDUATION_INSTANCE', None)

    for opt, val in opts:
        if opt in ('-l', '--logfile'):
            logfile = val
        elif opt in ('-p', '--port'):
            port = int(val)
        elif opt in ('--unencrypted',):
            use_encryption = False
        elif opt in ('--instance',):
            instance = val
        elif opt in ('-h', '--help'):
            usage()

    # Init twisted logger
    log.startLogging(file(logfile, 'a'))
    #log.callWithLogger(logger, func, *args, **kw)
    #        Utility method which wraps a function in a try:/except:, logs a
    #        failure if one occurrs, and uses the system's logPrefix.

    # Initiate the individuation instance
    module, classname = instance.split('/', 1)
    mod = dyn_import(module)
    cls = getattr(mod, classname)
    IndividuationServer.individuation = cls()
    print "Individuation is using: %s" % instance
    # TBD: Should Individuation be started once per session instead? Takes
    # more memory, but are there benefits we need, e.g. language control?

    if not use_encryption:
        private_key_file  = None
        certificate_file  = None
        client_cert_files = None
    else:
        private_key_file  = cereconf.SSL_PRIVATE_KEY_FILE
        certificate_file  = cereconf.SSL_CERTIFICATE_FILE
        client_cert_files = getattr(cereconf, 'INDIVIDUATION_CLIENT_CERT', None)
    server = SoapListener.TwistedSoapStarter(port = int(port),
                applications = IndividuationServer,
                private_key_file = private_key_file,
                certificate_file = certificate_file,
                client_cert_files = client_cert_files,
                encrypt = use_encryption)
    IndividuationServer.site = server.site # to make it global and reachable by Individuation (wrong, I know)
    # If sessions' behaviour should be changed (e.g. timeout):
    # server.site.sessionFactory = BasicSession
    server.run()
