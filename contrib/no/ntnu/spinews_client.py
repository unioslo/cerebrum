#! /usr/bin/env python
# -*- coding: utf-8 -*-
import sys, os, re, time, math
from xml.dom import expatbuilder

import cerebrum_path

import cereconf

from Cerebrum.lib.spinews.SignatureHandler import SignatureHandler
from Cerebrum.lib.spinews.spinews_services import *
from Cerebrum.lib.spinews.spinews_objects import *
from Cerebrum.lib.spinews.spinews_services_types import *
from ZSI.ServiceContainer import ServiceSOAPBinding

from httplib import HTTPConnection

from M2Crypto import SSL
from M2Crypto import X509


ca_cert = None
username = None
password = None

numb_groups = 0
numb_accounts = 0
numb_ous = 0
numb_aliases = 0
numb_homedirs = 0

class ExpatReaderClass(object):
    fromString = staticmethod(expatbuilder.parseString)
    fromStream = staticmethod(expatbuilder.parse)

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
    return cereconf.SSL_KEY_FILE_PASSWORD

def init_ssl():
    ctx = SSL.Context('sslv23')
    ctx.load_cert('/etc/cerebrum/ssl/spine.itea.ntnu.no.pem',callback=phrase_callback)
    ctx.load_verify_info(cafile='/etc/ssl/certs/itea-ca.crt')
    ## typical options for a client
    ctx_options = SSL.op_no_sslv2
    ctx.set_options(ctx_options)
    ctx.set_verify((SSL.verify_fail_if_no_peer_cert|SSL.verify_peer), 9)
    return ctx

## theTraceFile = open("soap_trace.log", 'wb', 16384)
theTraceFile = open("theTraceFile.log", 'wb', 1024)

samples = {}
stat_max_min = {}
def statreg(stat, t):
    if not stat in samples:
        samples[stat] = (0, 0.0, 0.0)
    n, sum, ssum = samples[stat]
    if not stat_max_min.get(stat):
        stat_max_min[stat] = []
    stat_max_min[stat].append(t)
    samples[stat] = (n+1, sum+t, ssum+t*t)

def statreset():
    samples.clear()

def statresult():
   global numb_groups, numb_accouts, numb_ous, numb_aliases, numb_homedirs
   print '%-10s  %s\t%s\t\t%s\t\t%s\t\t%s' % ('Operation',
                                             'Average',
                                             'Varying',
                                             'Max',
                                             'Min',
                                             'Runs')
   print '-------------------------------------------------------------------------------'
   for k,v in samples.items():
       n, sum, ssum = v
       mean=sum/n
       sd=math.sqrt(ssum/n-mean*mean)
       print "%-10s: %2.6f\t~%2.6f\t%2.6f\t%2.6f\t%d" % (k, mean,
                                                            sd,
                                                            max(stat_max_min[k]),
                                                            min(stat_max_min[k]),
                                                            n)
   print ''
   print 'groups pr. run\t\t:\t', numb_groups
   print 'accounts pr. run\t:\t', numb_accounts
   print 'ous pr. run\t\t:\t', numb_ous
   print 'aliases pr. run\t\t:\t', numb_aliases
   print 'homedirs pr. run\t:\t', numb_homedirs
   print ''


def set_username_password(uname, pwd):
    global username
    global password
    username = uname
    password = pwd

def get_ceresync_locator():
    return spinewsLocator()

def sign_request(port, username, password, useDigest=False):
    sigHandler = SignatureHandler(username, password, useDigest)
    port.binding.sig_handler = sigHandler
    return port

def get_ceresync_port():
    locator = get_ceresync_locator()
    port = locator.getspinePortType(readerclass=ExpatReaderClass, transport=CeresyncHTTPSConnection)
    global username
    global password
    sign_request(port, username, password)
    return port
 
def set_attributes(to_obj, from_obj):
    for key, value in from_obj._attrs.items():
        setattr(to_obj, key, value)
    return to_obj
    
def get_groups(groupspread, accountspread, inc_from=None):
    port = get_ceresync_port()
    request = getGroupsRequest()
    request._groupspread = groupspread
    request._accountspread = accountspread
    request._incremental_from = inc_from
    response = port.get_groups(request)
    ret_groups = []
    for group in response._group:
        grp = set_attributes(Group(), group)
        setattr(grp, 'members', group._member)
        setattr(grp, 'quarantines', group._quarantine)
        ret_groups.append(grp)
    return ret_groups
        

def get_accounts(accountspread, auth_type, inc_from=None):
    port = get_ceresync_port()
    request = getAccountsRequest()
    request._accountspread = accountspread
    request._auth_type = auth_type
    request._incremental_from = inc_from
    response = port.get_accounts(request)
    ret_accounts = []
    for account in response._account:
        acc = set_attributes(Account(), account)
        if account._quarantine:
            print 'account quarantine len: %s' % (len(account._quarantine))
        setattr(acc, 'quarantines', account._quarantine)
        ret_accounts.append(acc)
    return ret_accounts
        

def get_ous(inc_from=None):
    port = get_ceresync_port()
    request = getOUsRequest()
    request._incremental_from = inc_from
    response = port.get_ous(request)
    ret_ous = []
    for ou in response._ou:
        the_ou = set_attributes(Ou(), ou)
        setattr(the_ou, 'quarantines', ou._quarantine)
        ret_ous.append(the_ou)
    return ret_ous

def get_aliases(inc_from=None):
    port = get_ceresync_port()
    request = getAliasesRequest()
    request.__incremental_from = inc_from
    #import pdb;pdb.set_trace()
    response = port.get_aliases(request)
    ret_aliases = []
    for alias in response._alias:
        the_alias = set_attributes(Alias(), alias)
        ret_aliases.append(the_alias)
    return ret_aliases

def get_homedirs(status, hostname):
    port = get_ceresync_port()
    request = getHomedirsRequest()
    request._status = status
    request._hostname = hostname
    response = port.get_homedirs(request)
    ret_homedirs = []
    for homedir in response._homedir:
        hdir = set_attributes(Homedir(), homedir)
        homedir = None
        ret_homedirs.append(hdir)
    return ret_homedirs

def test_groups():
    before = time.time()
    grps = get_groups('group@ntnu', 'user@ansatt', None)
    statreg('groups',(time.time() - before))
    f = open('group.txt', 'wb', 16384)
    global numb_groups
    if numb_groups == 0:
        numb_groups = len(grps)
    for grp in grps:
        f.write(grp.name)
        f.write(':')
        f.write(str(grp.posix_gid))
        f.write(':')
        i = 0
        for quar in grp.quarantines:
            if i > 0:
                f.write(',')
            i += 1
            f.write(quar)
        f.write(':')
        i = 0
        for member in grp.members:
            if i > 0:
                f.write(',')
            i += 1
            f.write(member)
        f.write('\n')
    f.flush()
    f.close()

def test_accounts():
    before = time.time()
    accs = get_accounts('user@stud', 'MD5-crypt', None)
    statreg('accounts', (time.time() - before))
    f = open('accouns.txt', 'wb', 16384)
    global numb_accounts
    if numb_accounts == 0:
        numb_accounts = len(accs)
    for acc in accs:
        f.write( acc.name)
        f.write(':')
        f.write(acc.passwd )
        f.write(':')
        f.write(acc.homedir)
        f.write(':')
        f.write(acc.home)
        f.write(':')
        f.write(acc.disk_path)
        f.write(':')
        f.write(acc.disk_host)
        f.write(':')
        try:
            f.write(acc.gecos)
        except UnicodeEncodeError, e:
            f.write('norwegian chars')
        f.write(':')
        f.write(acc.shell)
        f.write(':')
        f.write(acc.shell_name )
        f.write(':')
        f.write(str(acc.posix_uid))
        f.write(':')
        f.write(str(acc.posix_gid))
        f.write(':')
        f.write(acc.primary_group)
        f.write(':')
        f.write(str(acc.owner_id))
        f.write(':')
        f.write(acc.owner_group_name)
        f.write(':')
        p_aff = 'None'
        if acc.primary_affiliation:
            p_aff = acc.primary_affiliation
        f.write(p_aff)
        f.write(':')
        f.write(str(acc.primary_ou_id))
        f.write(':')
        i = 0
        for quar in acc.quarantines:
            if i > 0:
                f.write(';')
            i += 1
            f.write(quar)
        f.write('\n')
    f.flush()
    f.close()

def test_ous():
    before = time.time()
    ous = get_ous()
    statreg('ous', (time.time() - before))
    f = open('ous.txt', 'wb', 16384)
    global numb_ous
    if numb_ous == 0:
        numb_ous = len(ous)
    for ou in ous:
        f.write(str(ou.id))
        f.write(':')
        try:
            f.write(ou.name)
        except UnicodeEncodeError, e:
            f.write('Norwegia chars')
        f.write(':')
        try:
            f.write(ou.acronym)
        except UnicodeEncodeError, e:
            f.write('Norwegia chars')
        f.write(':')
        try:
            f.write(ou.short_name)
        except UnicodeEncodeError, e:
            f.write('Norwegia chars')
        f.write(':')
        try:
            f.write(ou.display_name)
        except UnicodeEncodeError, e:
            f.write('Norwegian chars')
        f.write(':')
        try:
            f.write(ou.sort_name)
        except UnicodeEncodeError, e:
            f.write('Norwegian chars')
        f.write(':')
        f.write(str(ou.parent_id))
        f.write(':')
        f.write(ou.email)
        f.write(':')
        f.write(ou.url)
        f.write(':')
        f.write(ou.phone)
        f.write(':')
        p_address = 'None'
        if ou.post_address:
            p_address = ou.post_address
        f.write(p_address)
        f.write(':')
        f.write(ou.stedkode)
        f.write(':')
        p_stedkode = 'None'
        if ou.parent_stedkode:
            p_stedkode = ou.parent_stedkode
        f.write(p_stedkode)
        f.write(':')
        i = 0
        for quar in ou.quarantines:
            if i > 0:
                f.write(',')
            i += 1
            f.write(quar)
        f.write('\n')
    f.flush()
    f.close()

def test_aliases():
    before = time.time()
    aliases = get_aliases(None)
    statreg('aliases', (time.time() - before))
    f = open('aliases.txt', 'wb', 16384)
    global numb_aliases
    if numb_aliases == 0:
        numb_aliases = len(aliases)
    for alias in aliases:
        f.write(alias.local_part)
        f.write(':')
        f.write(alias.domain)
        f.write(':')
        p_addr_local_part = ''
        if alias.primary_address_local_part:
            p_addr_local_part = alias.primary_address_local_part
        f.write(p_addr_local_part)
        f.write(':')
        p_addr_domain = ''
        if alias.primary_address_domain:
            p_addr_domain = alias.primary_address_domain
        f.write(p_addr_domain)
        f.write(':')
        f.write(str(alias.address_id))
        f.write(':')
        f.write(alias.server_name)
        f.write(':')
        f.write(str(alias.account_id))
        f.write(':')
        f.write(alias.account_name)
        f.write('\n')
    f.flush()
    f.close()       
 
def test_homedirs():
    before = time.time()
    homedirs = get_homedirs('not_created', 'yeti.stud.ntnu.no')
    statreg('homedirs', (time.time() - before))
    f = open('homedirs.txt', 'wb', 16384)
    global numb_homedirs
    if numb_homedirs == 0:
        numb_homedirs = len(homedirs)
    for dir in homedirs:
        f.write(str(dir.homedir_id))
        f.write(':')
        f.write(dir.disk_path)
        f.write(':')
        f.write(dir.home)
        f.write(':')
        f.write(dir.homedir)
        f.write(':')
        f.write(dir.account_name)
        f.write(':')
        f.write(str(dir.posix_uid))
        f.write(':')
        f.write(str(dir.posix_gid))
        f.write('\n')
    f.flush()
    f.close()

def test_clients(count):

    set_username_password('bootstrap_account', 'blippE10')
    for i in range(count):
        print 'groups'
        test_groups()
        print 'accounts'
        test_accounts()
        print 'ous'
        test_ous()
        print 'aliases'
        test_aliases()
        print 'homedirs'
        test_homedirs()
        sys.stderr.write('Run: %d\n' % (i+1))
    statresult()
    
    
def main(argv):
    global ca_cert
    ca_cert = X509.load_cert('/etc/ssl/certs/itea-ca.crt')
    test_clients(1)
 
if __name__ == '__main__':
    main(sys.argv)
