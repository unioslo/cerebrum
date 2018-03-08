#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2010-2016 University of Oslo, Norway
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

"""This file provides a SOAP service for the Individuation service at UiO.

This is the glue between Cerebrum and twisted's soap server, as the Cerebrum
specific functionality should not know anything about twisted.

Each public method's docstring is the string that is put into the wsdl file for
the web service, and is therefore given to those who should use the web service.

Note that the logger is twisted's own logger and not Cerebrum's, since twisted
has special needs, as it works with callbacks and runs in threads - it must for
instance not be blocked.

"""

import getopt
import sys

from twisted.python import log

from rpclib.model.complex import ComplexModel, Iterable
from rpclib.model.primitive import String, Integer, Boolean
# Note the difference between rpc and the static srpc - the former sets the
# first parameter as the current MethodContext. Very nice if you want
# environment details.
from rpclib.decorator import rpc

import cerebrum_path
from cisconf import individuation as cisconf
from Cerebrum.Utils import Messages, dyn_import
from Cerebrum.modules.cis import SoapListener, faults

del cerebrum_path


class Account(ComplexModel):
    # FIXME: define namespace properly
    __namespace__ = 'account'
    uname = String
    priority = Integer
    status = String


class IndividuationServer(SoapListener.BasicSoapServer):
    """Defining the SOAP actions that should be available to clients. All
    those actions are decorated as an rpc, defining what parameters the
    methods accept, types and what is returned.

    Note that the service classes will _not_ be instantiated by rpclib. Instead,
    rpclib creates a MethodContext instance for each call and feeds it to the
    public methods. To avoid thread conflicts, you should use this ctx instance
    for storing local variables, and _not_ the service class.

    """

    # Require the session ID in the client's header
    __in_header__ = SoapListener.SessionHeader

    # Respond with a header with the current session ID
    __out_header__ = SoapListener.SessionHeader

    # The class where the Cerebrum-specific functionality is done. This is
    # instantiated per call, to avoid thread conflicts.
    cere_class = None

    # The hock for the site object
    site = None

    @rpc(String, _returns=Boolean)
    def set_language(ctx, language):
        """Sets what language feedback messages should be returned in."""
        # TODO: improve validation of the language code
        if language not in ('en', 'no'):
            return False
        ctx.udc['session']['msgs'].lang = language
        return True

    @rpc(String, String, _returns=Iterable(Account))
    def get_usernames(ctx, id_type, ext_id):
        """Based on id-type and the ID, identify a person in Cerebrum and return
        a list of the person's accounts and their status. If the person exist
        but doesn't have an account an empty list is returned. If no person
        match the id_type and ID an exception is thrown.

        The list is sorted by the person's user priorities, with the primary
        account first.

        The types of user statuses are:

          - *Inactive*: if the account is reserved, deleted or expired, or if it
            has an active quarantine. Note that some quarantines are ignored,
            e.g. autopassord, since the user is still able to use the forgotten
            password service with this quarantine.
          - *PasswordQuarantined*: if the account is not inactive, but has a
            quarantine of type 'autopassord'.
          - *Active*: if the account is active and without quarantine.

        """
        ret = []
        # get_person_accounts returns a list of dicts on the form:
        # [{'uname': '...', 'priority': '...', 'status': '...'}, ...]
        for acc in ctx.udc['individuation'].get_person_accounts(id_type,
                                                                ext_id):
            a = Account()
            for k, v in acc.items():
                setattr(a, k, v)
            ret.append(a)
        return ret

    @rpc(String, String, String, String, String, _returns=Boolean)
    def generate_token(ctx, id_type, ext_id, username, phone_no, browser_token):
        """Send a token by SMS to the person's phone and store the token in
        Cerebrum. All input must match the same, existing person in Cerebrum,
        include the phone number. Phone numbers are only retrieved for some
        source systems, depending on the configuration of the service.

        """
        return ctx.udc['individuation'].generate_token(id_type, ext_id,
                                                       username, phone_no,
                                                       browser_token)

    @rpc(String, String, String, _returns=Boolean)
    def check_token(ctx, username, token, browser_token):
        """Check if given token is the same token as the last one generated
        through L{generate_token} for the given user. This is to validate that
        the person has gotten the token through its own cell phone.

        If the token is correct, it means that the user is able to change its
        password.

        Throws an exception if the token is too old, or in case of too many
        failed attempts.

        """
        return ctx.udc['individuation'].check_token(username, token,
                                                    browser_token)

    @rpc(String, _returns=Boolean)
    def abort_token(ctx, username):
        """Remove the temporary token for the given user from Cerebrum. This
        should be used in case the user wants to abort the process of setting a
        new password.

        """
        return ctx.udc['individuation'].delete_token(username)

    @rpc(String, String, String, String, _returns=Boolean)
    def set_password(ctx, username, new_password, token, browser_token):
        """Set a new password for a given user. Note that both the token and the
        browser token must match the ones stored in Cerebrum. Also, the password
        must match the instance' password criterias.

        """
        return ctx.udc['individuation'].set_password(username, new_password,
                                                     token, browser_token)

    @rpc(String, _returns=Boolean)
    def validate_password(ctx, password):
        """
        Check if a given password is good enough.

        Returns True of the password meets the instance' password criteria.
        An exception is thrown otherwise.

        :param password: the password to be validated
        :type password: str
        """
        return bool(ctx.udc['individuation'].validate_password(password,
                                                               '',
                                                               False))

    @rpc(String, String, _returns=Boolean)
    def validate_password_for_account(ctx, account_name, password):
        """
        Check if a given password is good enough.

        Returns True of the password meets the instance' password criteria.
        An exception is thrown otherwise.

        :param account_name: the account name to be used or ''
        :type account_name: str
        :param password: the password to be validated
        :type password: str
        """
        return bool(ctx.udc['individuation'].validate_password(password,
                                                               account_name,
                                                               False))

    @rpc(String, String, Boolean, _returns=String)
    def structured_password_validation(ctx, password, account_name, structured):
        """
        Check if a given password is good enough.

        :param password: the password to be validated
        :type password: str
        :param account_name: the account name to be used or ''
        :type account_name: str
        :param structured: whether to ask for a strctured (json) output
        :type structured: bool

        When `structured` is True:
        Returns a json structure describing the requirements for each
        performed check as well as error messages on failure.

        When `structured` is False:
        Returns 'OK' on success and throws exception on failure.
        """
        return ctx.udc['individuation'].validate_password(password,
                                                          account_name,
                                                          structured)


# Add the session events:
IndividuationServer.event_manager.add_listener(
    'method_call',
    SoapListener.on_method_call_session)
IndividuationServer.event_manager.add_listener(
    'method_return_object',
    SoapListener.on_method_exit_session)


# And then the individuation specific events:
def _on_method_call(ctx):
    """
    Event method for fixing the individuation functionality, like language.
    """
    # TODO: the language functionality may be moved into SoapListener? It is
    # probably usable by other services too.
    ctx.udc['individuation'] = ctx.service_class.cere_class()
    if 'msgs' not in ctx.udc['session']:
        ctx.udc['session']['msgs'] = Messages(
            text=ctx.udc['individuation'].messages)
IndividuationServer.event_manager.add_listener('method_call', _on_method_call)


def _on_method_exception(ctx):
    """Event for updating raised exceptions to return a proper error message in
    the chosen language. The individuation instance could then raise errors with
    a code that corresponds to a message, and this event updates the error with
    the message in the correct language.
    """
    if isinstance(ctx.out_error, faults.EndUserFault):
        err = ctx.out_error
        try:
            err.faultstring = (ctx.udc['session']['msgs'][err.faultstring] %
                               err.extra)
        except KeyError, e:
            log.msg('WARNING: Unknown error: %s - %s' % (err.faultstring, e))
IndividuationServer.event_manager.add_listener('method_exception_object',
                                               _on_method_exception)


# When a call is processed, it has to be closed:
def _on_method_exit(ctx):
    """Event for cleaning up the individuation instances, i.e. close the
    database connections. Since twisted runs all calls in a pool of threads, we
    can not trust __del__."""
    # TODO: is this necessary any more, as we now are storing it in the method
    # context? Are these deleted after each call?
    if 'individuation' in ctx.udc:
        ctx.udc['individuation'].close()
IndividuationServer.event_manager.add_listener('method_return_object',
                                               _on_method_exit)
IndividuationServer.event_manager.add_listener('method_exception_object',
                                               _on_method_exit)


def usage(exitcode=0):
    print """Usage: %s [-p <port number] [-l logfile] [--unencrypted]

Starts up the Individuation webservice on a given port. Please note that
config (cisconf) contains more settings for the service.

  -p
  --port num        Run on alternative port than defined in cisconf.PORT.

  --interface ADDR  What interface the server should listen to. Overrides
                    cisconf.INTERFACE. Default: 0.0.0.0

  -l
  --logfile:        Where to log. Overrides cisconf.LOG_FILE.

  --instance        The individuation instance which should be used. Defaults
                    to cisconf.CEREBRUM_CLASS. E.g:
                        Cerebrum.modules.cis.Individuation/Individuation
                    or:
                        Cerebrum.modules.cis.UiAindividuation/Individuation

  --unencrypted     Don't use HTTPS. All communications goes unencrypted, and
                    should only be used for testing.

  -h
  --help            Show this and quit.
    """
    sys.exit(exitcode)


if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'p:l:h',
                                   ['port=', 'unencrypted', 'logfile=',
                                    'help', 'instance=', 'interface='])
    except getopt.GetoptError, e:
        print e
        usage(1)

    use_encryption = True
    port = getattr(cisconf, 'PORT', 0)
    logfilename = getattr(cisconf, 'LOG_FILE', None)
    instance = getattr(cisconf, 'CEREBRUM_CLASS', None)
    interface = getattr(cisconf, 'INTERFACE', None)
    log_prefix = getattr(cisconf, 'LOG_PREFIX', None)
    log_formatters = getattr(cisconf, 'LOG_FORMATTERS', None)

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
        else:
            print "Unknown argument: %s" % opt
            usage(1)

    # Get the individuation class and give it to the server
    module, classname = instance.split('/', 1)
    mod = dyn_import(module)
    cls = getattr(mod, classname)
    IndividuationServer.cere_class = cls
    log.msg("DEBUG: Individuation is using: %s" % instance)
    # TBD: Should Individuation be started once per session instead? Takes
    # more memory, but are there benefits we need, e.g. language control?

    private_key_file = None
    certificate_file = None
    client_ca = None
    fingerprints = None

    if interface:
        SoapListener.TwistedSoapStarter.interface = interface

    if use_encryption:
        private_key_file = cisconf.SERVER_PRIVATE_KEY_FILE
        certificate_file = cisconf.SERVER_CERTIFICATE_FILE
        client_ca = cisconf.CERTIFICATE_AUTHORITIES
        fingerprints = getattr(cisconf, 'FINGERPRINTS', None)

        server = SoapListener.TLSTwistedSoapStarter(
            port=int(port),
            applications=IndividuationServer,
            private_key_file=private_key_file,
            certificate_file=certificate_file,
            client_ca=client_ca,
            client_fingerprints=fingerprints,
            logfile=logfilename,
            log_prefix=log_prefix,
            log_formatters=log_formatters)
    else:
        server = SoapListener.TwistedSoapStarter(
            port=int(port),
            applications=IndividuationServer,
            logfile=logfilename,
            log_prefix=log_prefix,
            log_formatters=log_formatters)
    IndividuationServer.site = server.site

    # We want the sessions to be simple dicts, for now:
    server.site.sessionFactory = SoapListener.SessionCacher
    # Set the timeout to something appropriate:
    SoapListener.SessionCacher.sessionTimeout = 600  # 10 minutes
    server.run()
