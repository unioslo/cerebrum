import sys, os, re, time

import cerebrum_path

from SignatureHandler import *
from Cerebrum.lib.spinews.spinews_services import *
from Cerebrum.lib.spinews.spinews_services_types import *
from ZSI.ServiceContainer import ServiceSOAPBinding

from httplib import HTTPConnection

from M2Crypto import SSL
from M2Crypto import X509

ca_cert = None
class CeresyncHTTPSConnection(HTTPConnection):
    default_port = 443

    def __init__(self, host, port=None, strict=None):
        HTTPConnection.__init__(self, host, port, strict)
        self.host = host
        self.port = port
        if re.search(':', self.host):
            tab = self.host.split(':')
            self.host = tab[0]
            self.port = int(tab[1])
        if not self.port:
            self.port = self.default_port

    def connect(self):
        "Connect to a host on a given (SSL) port."
        ctx = init_ssl()
        sock = SSL.Connection(ctx)
        sock.connect((self.host, self.port))
        server_cert = sock.get_peer_cert()
        if server_cert:
            if not server_cert.verify(ca_cert.get_pubkey()):
                server_cert_issuer = server_cert.get_issuer()
                mess = 'Unknown CA: %s\n' % server_cert_issuer
                sys.stderr.write(mess)
                sock.clear()
                sock.close()
                sys.exit(1)
            else:
                self.sock = sock
        else:
            sys.stderr.write('No certificae from server\n')
            sock.clear()
            sock.close()
            sys.exit(2)

def phrase_callback(v, prompt1='p1', prompt2='p2'):
    return ''

def init_ssl():
    ctx = SSL.Context('sslv23')
    ctx.load_cert('/etc/cerebrum/ssl/spine.itea.ntnu.no.pem',callback=phrase_callback)
    ctx.load_verify_info(cafile='/etc/ssl/certs/itea-ca.crt')
    ## typical options for a client
    ctx_options = SSL.op_no_sslv2
    ctx.set_options(ctx_options)
    ctx.set_verify((SSL.verify_fail_if_no_peer_cert|SSL.verify_peer), 9)
    return ctx

kw = {'tracefile' : sys.stdout, 'transport' : CeresyncHTTPSConnection }

def get_ceresync_port():
    locator = spinewsLocator()
    return locator.getspinePortType(**kw)

def sign_request(port, username, password):
    sigHandler = SignatureHandler(username, password, False)
    port.binding.sig_handler = sigHandler
 
def get_groups(username, password, groupspread, accountspread, inc_from=None):
    port = get_ceresync_port()
    sign_request(port, username, password)
    request = getGroupsRequest()
    request._groupspread = groupspread
    request._accountspread = accountspread
    request._incremental_from = inc_from
    return port.get_groups(request)

def get_accounts(username, password, accountspread, inc_from=None):
    port = get_ceresync_port()
    sign_request(port, username, password)
    request = getAccountsRequest()
    request._accountspread = accountspread
    request._incremental_from = inc_from
    return port.get_accounts(request)

def get_ous(username, password, inc_from=None):
    port = get_ceresync_port()
    sign_request(port, username, password)
    request = getOUsRequest()
    request._incremental_from = inc_from
    return port.get_ous(request)

def get_aliases(username, password, inc_from=None):
    port = get_ceresync_port()
    sign_request(port, username, password)
    request = getAliasesRequest()
    request.__incremental_from = inc_from
    return port.get_aliases(request)

def get_homedirs(username, password, status):
    port = get_ceresync_port()
    sign_request(port, username, password)
    request = getHomedirsRequest()
    request._status = status
    return port.get_homedirs(request)

def test_groups():
    before = time.time()
    response = get_groups('hjalla', 'gork', 'group@ntnu', 'user@ansatt', None)
    print "Get groups time: %f" % (time.time() - before)
    for group in response._group:
        ## list
        members = group._member
        ## list
        quarantines = group._quarantine
        ## dict
        grp_name = group._attrs.get('name', '')
        grp_posix = group._attrs.get('posix_gid', '')
        print "Groupname: ", grp_name
        print "Groupposix: ", grp_posix
        for mem in members:
            print "\tmember: ", mem
        for quar in quarantines:
            print "\tquarantine: ", quar

def test_accounts():
    before = time.time()
    response = get_accounts('hjalla', 'gork', 'user@ansatt', None)
    print "Get accounts time: %f" % (time.time() - before)
    for acc in response._account:
        quarantine = acc._quarantine
        for k in acc.attrs.keys():
            print '%s: %s' % (k, acc._attrs.get(k, ''))
        print 'quarantin', quarantine

def test_ous():
    before = time.time()
    response = get_ous('hjalla', 'gork', None)
    print "Get ous time: %f" % (time.time() - before)
    for ou in response._ou:
        quarantine = ou._quarantine
        for k in ou._attrs.keys():
            print '%s: %s' % (k, ou._attrs.get(k, ''))
        print 'quarantine: %s', quarantine

def test_aliases():
    before = time.time()
    reponse = get_aliases('hjalla', 'gork', None)
    print "Get alises time: %f" % (time.time() - before)
 
def test_homedirs():
    before = time.time()
    response = get_homedirs('hjalla', 'gork', None)
    print "Get homedirs time: %f" % (time.time() - before)
    
def main(argv):
    global ca_cert
    ca_cert = X509.load_cert('/etc/ssl/certs/itea-ca.crt')
    test_groups()
    ## test_accounts()
    ## test_ous()
    test_aliases()
    test_homedirs()
 
if __name__ == '__main__':
    main(sys.argv)
