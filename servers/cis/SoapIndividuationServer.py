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

Note that the logger is twisted's own logger and not Cerebrum's. Since twisted
works in parallell the logger should not be blocked. Due to this, the format of
the logs is not equal to the rest of Cerebrum. This might be something to work
on later.

"""

import sys, socket, traceback
import getopt

import cerebrum_path, cereconf
from Cerebrum.modules.cis import Individuation, SoapListener
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
    """Defining the SOAP actions that should be available to clients. All
    those actions are decorated as a rpc, defining what parameters the methods
    accept, types and what is returned.

    Note that an instance of this class is created for each incoming call."""

    # The class where the Cerebrum-specific functionality is done. This is
    # instantiated per call, to avoid thread conflicts.
    cere_class = None

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
            cache['msgs'] = Messages(text=self.individuation.messages)
        return cache

    def call_wrapper(self, call, params):
        """Subclassing the call wrapper to instantiate the Individuation
        instance and to handle exceptions in a soap-wise manner."""
        try:
            self.individuation = self.cere_class()
            self.cache = self._get_cache(params.session_id)
            return super(IndividuationServer, self).call_wrapper(call, params)
        except KeyboardInterrupt: # don't catch signals like ctrl+c
            raise
        except Errors.CerebrumRPCException, e:
            msg = self.cache['msgs'][e.args[0]] % e.args[1:]
            raise Fault(faultstring=e.__doc__ + ': ' + msg)
        except Exception, e:
            # If anything breaks in here, it will not get logged. Beware!
            log.msg('ERROR: Unhandled exception: %s' % type(e))
            log.err(e)
            log.msg(traceback.format_exc())

            # Don't want the client to know too much about unhandled errors, so
            # return a generic error.
            raise Fault(faultstring='Unknown error')
        finally:
            # should always close the instance and remove it, as the garbage
            # collector might not work correctly in these threads
            if hasattr(self, 'individuation'):
                self.individuation.close()
                del self.individuation

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

Starts up the Individuation webservice on a given port. Please note that
cereconf.INDIVIDUATION* contains more settings for the service.

  -p
  --port num        Run on alternative port than defined in cereconf.

  --interface ADDR  What interface the server should listen to 
                    (default: 0.0.0.0)

  -l
  --logfile:        Where to log

  --instance        The individuation instance which should be used. Defaults
                    to cereconf.INDIVIDUATION_INSTANCE. E.g:
                        Cerebrum.modules.cis.Individuation/Individuation
                    or:
                        Cerebrum.modules.cis.UiAindividuation/Individuation

  --unencrypted     Don't use https

  -h
  --help            Show this and quit
    """
    sys.exit(exitcode)


if __name__=='__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'p:l:h',
                                   ['port=', 'unencrypted', 'logfile=',
                                    'help', 'instance=', 'interface='])
    except getopt.GetoptError, e:
        print e
        usage(1)

    use_encryption = True
    port        = getattr(cereconf, 'INDIVIDUATION_SERVICE_PORT', 0)
    logfilename = getattr(cereconf, 'INDIVIDUATION_SERVICE_LOGFILE', None)
    instance    = getattr(cereconf, 'INDIVIDUATION_INSTANCE', None)
    interface   = None

    for opt, val in opts:
        if opt in ('-l', '--logfile'):
            logfilename = val
        elif opt in ('-p', '--port'):
            port = int(val)
        elif opt in ('--unencrypted',):
            use_encryption = False
        elif opt in ('--instance',):
            instance = val
        elif opt in ('--interface',):
            interface = val
        elif opt in ('-h', '--help'):
            usage()

    # Get the individuation class and give it to the server
    module, classname = instance.split('/', 1)
    mod = dyn_import(module)
    cls = getattr(mod, classname)
    IndividuationServer.cere_class = cls
    log.msg("Individuation is using: %s" % instance)
    # TBD: Should Individuation be started once per session instead? Takes
    # more memory, but are there benefits we need, e.g. language control?

    private_key_file  = None
    certificate_file  = None
    client_ca         = None
    fingerprints      = None

    if use_encryption:
        private_key_file  = cereconf.SSL_PRIVATE_KEY_FILE
        certificate_file  = cereconf.SSL_CERTIFICATE_FILE
        client_ca         = cereconf.INDIVIDUATION_CLIENT_CA
        fingerprints      = getattr(cereconf, 'INDIVIDUATION_CLIENT_FINGERPRINTS', None)
    if interface:
        SoapListener.TwistedSoapStarter.interface = interface

    server = SoapListener.TwistedSoapStarter(port = int(port),
                applications = IndividuationServer,
                private_key_file = private_key_file,
                certificate_file = certificate_file,
                client_ca = client_ca,
                encrypt = use_encryption,
                client_fingerprints = fingerprints,
                logfile = logfilename)
    IndividuationServer.site = server.site # to make it global and reachable by Individuation (wrong, I know)

    # If sessions' behaviour should be changed (e.g. timeout):
    # server.site.sessionFactory = BasicSession
    server.run()
