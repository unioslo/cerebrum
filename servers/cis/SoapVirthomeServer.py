import sys
import getopt
from rpclib.model.complex import ComplexModel, Iterable
from rpclib.model.primitive import String, Integer, Boolean
from rpclib.decorator import rpc

#from Cerebrum import Errors
from Cerebrum.Utils import dyn_import
from Cerebrum.modules.cis import SoapListener, faults
from Cerebrum.modules.cis.Utils import Unicode, DateTime

from cisconf import webidservice as cisconf

NAMESPACE = 'webid'
TNS = 'webid'

# Objects that are passed to and fro'
class InviteResult(ComplexModel):
    __namespace__ = NAMESPACE
    __tns__ = TNS
    confirmation_key = String
    match_user = String
    match_user_email = String
    group_id = Integer

class CreateResult(ComplexModel):
    __namespace__ = NAMESPACE
    __tns__ = TNS
    group_id = Integer
    group_name = String

class GroupMember(ComplexModel):
    __namespace__ = NAMESPACE
    __tns__ = TNS
    member_id = Integer
    member_type = String
    member_name = String
    owner_name = Unicode
    email_address = Unicode

class Group(ComplexModel):
    __namespace__ = NAMESPACE
    __tns__ = TNS
    group_id = Integer
    name = String
    description = Unicode

class VirthomeService(SoapListener.BasicSoapServer):
    __namespace__ = NAMESPACE
    __tns__ = TNS

    # Require the session ID in the client's header
    __in_header__ = SoapListener.SessionHeader
    # Respond with a header with the current session ID
    __out_header__ = SoapListener.SessionHeader

    # The class where the Cerebrum-specific functionality is done. This is
    # instantiated per call, to avoid thread conflicts.
    cere_class = None

    # The hock for the site object
    site = None

    @rpc(Unicode, _returns=Unicode, _throws=faults.EndUserFault)
    def echo(ctx, text):
        return text


    @rpc(String, String, DateTime, String, String, _returns=Boolean, _throws=faults.EndUserFault)
    def fedaccount_assert(ctx, account_name, email, expire_date=None,
            human_first_name=None, human_last_name=None):
        return ctx.udc['webid'].fedaccount_assert(account_name, 
                                                  email, 
                                                  expire_date, 
                                                  human_first_name, 
                                                  human_last_name)

    @rpc(String, String, String, Integer, _returns=InviteResult, _throws=faults.EndUserFault)
    def group_invite_user(ctx, group_name, inviter_name, email, timeout):
        return ctx.udc['webid'].group_invite_user(group_name, inviter_name, email, timeout)

    @rpc(String, String, String, String, String, _returns=CreateResult, _throws=faults.EndUserFault)
    def group_create(ctx, group_name, group_desc, owner_name, group_url, group_forward):
        return ctx.udc['webid'].group_create(group_name, 
                                             group_desc, 
                                             owner_name, 
                                             group_url, 
                                             group_forward)

    @rpc(String, _returns=String, _throws=faults.EndUserFault)
    def group_disable(ctx, group):
        return ctx.udc['webid'].group_disable(group)
        
    @rpc(String, _returns=Iterable(GroupMember), _throws=faults.EndUserFault)
    def list_group_members(ctx, group):
        return ctx.udc['webid'].list_group_members(group)
        
    @rpc(String, _returns=Iterable(Group), _throws=faults.EndUserFault)
    def list_group_memberships(ctx, user):
        return ctx.udc['webid'].list_group_memberships(user)
        

# The group service events:
def _event_setup_virthome(ctx):
    """Event method for setting up/instantiating the context.
    """
    ctx.udc['webid'] = ctx.service_class.cere_class()


def _event_cleanup(ctx):
    """Event for cleaning up the groupinfo instances, i.e. close the
    database connections. Since twisted runs all calls in a pool of threads, we
    can not trust __del__."""
    # TODO: is this necessary any more, as we now are storing it in the method
    # context? Are these deleted after each call?
    if ctx.udc.has_key('webid'):
        ctx.udc['webid'].close()

# Add session support to the service:
add_listener = VirthomeService.event_manager.add_listener
add_listener('method_call', SoapListener.on_method_call_session)
add_listener('method_return_object', SoapListener.on_method_exit_session)

# Add instance specific events:
add_listener('method_call', _event_setup_virthome)
add_listener('method_return_object', _event_cleanup)
add_listener('method_exception_object', _event_cleanup)

def usage(exitcode=0):
    print """Usage: %s [-p <port number] [-l logfile] [--unencrypted]

Starts up the WebIDService webservice on a given port. Please note that config
(cisconf) contains more settings for the service.

  -p
  --port num        Run on alternative port than defined in cisconf.PORT.

  --interface ADDR  What interface the server should listen to. Overrides
                    cisconf.INTERFACE. Default: 0.0.0.0

  -l
  --logfile:        Where to log. Overrides cisconf.LOG_FILE.

  --instance        The individuation instance which should be used. Defaults
                    to what is defined in cisconf.CEREBRUM_CLASS, e.g:
                        Cerebrum.modules.cis.GroupInfo/GroupInfo

  --unencrypted     Don't use HTTPS. All communications goes unencrypted, and
                    should only be used for testing.

  -h
  --help            Show this and quit.
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
    port        = getattr(cisconf, 'PORT', 0)
    logfilename = getattr(cisconf, 'LOG_FILE', None)
    instance    = getattr(cisconf, 'CEREBRUM_CLASS', None)
    interface   = getattr(cisconf, 'INTERFACE', None)
    log_prefix  = getattr(cisconf, 'LOG_PREFIX', None)
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

    # Get the service tier class and give it to the server
    module, classname = instance.split('/', 1)
    mod = dyn_import(module)
    cls = getattr(mod, classname)
    VirthomeService.cere_class = cls

    private_key_file  = None
    certificate_file  = None
    client_ca         = None
    fingerprints      = None

    if interface:
        SoapListener.TwistedSoapStarter.interface = interface

    if use_encryption:
        private_key_file  = cisconf.SERVER_PRIVATE_KEY_FILE
        certificate_file  = cisconf.SERVER_CERTIFICATE_FILE
        client_ca         = cisconf.CERTIFICATE_AUTHORITIES
        fingerprints      = getattr(cisconf, 'FINGERPRINTS', None)

        server = SoapListener.TLSTwistedSoapStarter(port = int(port),
                        applications = VirthomeService,
                        private_key_file = private_key_file,
                        certificate_file = certificate_file,
                        client_ca = client_ca,
                        client_fingerprints = fingerprints,
                        logfile = logfilename,
                        log_prefix = log_prefix,
                        log_formatters=log_formatters)
    else:
        server = SoapListener.TwistedSoapStarter(port = int(port),
                                    applications = VirthomeService,
                                    logfile = logfilename,
                                    log_prefix = log_prefix,
                                    log_formatters=log_formatters)
    VirthomeService.site = server.site # to make it global and reachable by tier

    # We want the sessions to be simple dicts, for now:
    server.site.sessionFactory = SoapListener.SessionCacher
    # Set the timeout to something appropriate:
    SoapListener.SessionCacher.sessionTimeout = 600 # = 10 minutes

    server.run()
