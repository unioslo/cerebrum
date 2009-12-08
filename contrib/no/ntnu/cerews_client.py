#! /usr/bin/env python
# -*- coding: utf-8 -*-
import sys, os, re, time, math, datetime

import cerebrum_path

import cereconf
from optparse import OptionParser

from Cerebrum.lib.cerews.SignatureHandler import SignatureHandler


from Cerebrum.lib.cerews.cerews_services import *
from Cerebrum.lib.cerews.cerews_services_types import *
from ZSI.ServiceContainer import ServiceSOAPBinding

from httplib import HTTPConnection

from M2Crypto import SSL
from M2Crypto import X509

from Cerebrum.lib.cerews.cerews_objects import Group, Account
from Cerebrum.lib.cerews.cerews_objects import Ou, Alias
from Cerebrum.lib.cerews.cerews_objects import Homedir, Person
from Cerebrum.lib.cerews.dom import DomletteReader

username = None
password = None

numb_groups = 0
numb_accounts = 0
numb_ous = 0
numb_aliases = 0
numb_homedirs = 0
numb_persons = 0


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
        if hasattr(cereconf, "CEREWS_HOST"):
            self.host = cereconf.CEREWS_HOST
        if hasattr(cereconf, "CEREWS_PORT"):
            self.port = cereconf.CEREWS_PORT
        if not self.port:
            self.port = self.default_port

    def connect(self):
        "Connect to a host on a given (SSL) port."
        ctx = init_ssl()
        self.sock = SSL.Connection(ctx)
        self.sock.connect((self.host, self.port))

def phrase_callback(v, prompt1='p1', prompt2='p2'):
    return cereconf.CEREWS_KEY_FILE_PASSWORD

def init_ssl():
    ctx = SSL.Context('sslv23')
    if hasattr(cereconf, "CEREWS_CA_PATH"):
        ctx.load_verify_info(capath=cereconf.CEREWS_CA_PATH)
    elif hasattr(cereconf, "CEREWS_CA_FILE"):
        ctx.load_verify_info(cafile=cereconf.CEREWS_CA_FILE)
    else:
        ## logging and axit maybe?
        print >> sys.stderr, 'could not load ca-certificates'
        sys.exit(1)
    ## typical options for a client
    ctx_options = SSL.op_no_sslv2
    ctx.set_options(ctx_options)
    ctx.set_verify((SSL.verify_fail_if_no_peer_cert|SSL.verify_peer), 9)
    return ctx

## theTraceFile = open("soap_trace.log", 'wb', 16384)
theTraceFile = open("soap_trace.log", 'wb', 16384)

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
    global numb_groups, numb_accouts, numb_ous, numb_aliases, numb_homedirs, numb_persons
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
    if numb_groups > 0:
        print 'groups pr. run\t\t:\t', numb_groups
    if numb_accounts > 0:
        print 'accounts pr. run\t:\t', numb_accounts
    if numb_ous > 0:
        print 'ous pr. run\t\t:\t', numb_ous
    if numb_aliases > 0:
        print 'aliases pr. run\t\t:\t', numb_aliases
    if numb_homedirs > 0:
        print 'homedirs pr. run\t:\t', numb_homedirs
    if numb_persons > 0:
        print 'persons pr. run\t\t:\t', numb_persons
    print ''


def set_username_password(uname, pwd):
    global username
    global password
    username = uname
    password = pwd

def get_ceresync_locator():
    return cerewsLocator()

def sign_request(port, username, password, useDigest=False):
    sigHandler = SignatureHandler(username, password, useDigest)
    port.binding.sig_handler = sigHandler
    return port

def get_ceresync_port():
    global theTraceFile
    locator = get_ceresync_locator()
    port = locator.getcerewsPortType(tracefile=theTraceFile, readerclass=DomletteReader, transport=CeresyncHTTPSConnection, scheme="https")
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

def get_persons(spread=None, inc_from=None):
    port = get_ceresync_port()
    request = getPersonsRequest()
    request._spread = spread
    request._incremental_from = inc_from
    response = port.get_persons(request)
    ret_persons = []
    for pers in response._person:
        thePerson = set_attributes(Person(), pers)
        thePerson.affiliations = pers._affiliation
        thePerson.quarantines = pers._quarantine
        thePerson.traits = pers._trait
        ret_persons.append(thePerson)
    return ret_persons

def get_changelogid():
    port = get_ceresync_port()
    request = getChangelogidRequest()
    response = port.get_changelogid(request)
    return response

def test_persons():
    global numb_persons
    before = time.time()
    persons = get_persons()
    statreg('persons',(time.time() - before))
    f = open('persons.txt', 'wb', 16384)
    if numb_persons == 0:
        numb_persons = len(persons)
    for pers in persons:
        f.write(str(pers.id))
        f.write(':')
        f.write(pers.export_id)
        f.write(':')
        if pers.type:
            f.write(pers.type)
        f.write(':')
        if pers.birth_date:
            f.write(pers.birth_date)
        f.write(':')
        if pers.nin:
            f.write(pers.nin)
        f.write(':')
        if pers.first_name:
            try:
                f.write(pers.first_name)
            except UnicodeEncodeError, e:
                f.write('Norwegian chars')
        f.write(':')
        if pers.last_name:
            try:
                f.write(pers.last_name)
            except UnicodeEncodeError, e:
                f.write('Norwegian chars')
        f.write(':')
        if pers.full_name:
            try:
                f.write(pers.full_name)
            except UnicodeEncodeError, e:
                f.write('Norwegian chars')
        f.write(':')
        if pers.display_name:
            try:
                f.write(pers.display_name)
            except UnicodeEncodeError, e:
                f.write('Norwegian chars')
        f.write(':')
        if pers.work_title:
            try:
                f.write(pers.work_title)
            except UnicodeEncodeError, e:
                f.write('Norwegian chars')
        f.write(':')
        if pers.primary_account:
            f.write(pers.primary_account)
        f.write(':')
        if pers.primary_account_name:
            f.write(pers.primary_account_name)
        f.write(':')
        if pers.primary_account_password:
            f.write(pers.primary_account_password)
        f.write(':')
        if pers.email:
            f.write(pers.email)
        f.write(':')
        if pers.address_text:
            f.write(pers.address_text)
        f.write(':')
        if pers.city:
            f.write(pers.city)
        f.write(':')
        if pers.postal_number:
            f.write(pers.postal_number)
        f.write(':')
        if pers.phone:
            f.write(pers.phone)
        f.write(':')
        if pers.url:
            f.write(pers.url)
        f.write(':')
        i = 0
        for quar in pers.quarantines:
            if i > 0:
                f.write(',')
            i += 1
            f.write(quar)
        f.write(':')
        i = 0
        for aff in pers.affiliations:
            if i > 0:
                f.write(',')
            i += 1
            f.write(aff)
        f.write(':')
        i = 0
        for trait in pers.traits:
            if i > 0:
                f.write(',')
            i += 1
            f.write(quar)
        f.write('\n')
    f.flush()
    f.close()

    
def test_groups():
    before = time.time()
    grps = get_groups('group@ntnu', 'user@stud', None)
    statreg('groups',(time.time() - before))
    f = open('groups.txt', 'wb', 16384)
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
    ## accs = get_accounts('user@kerberos', 'PGP-kerberos', None)
    accs = get_accounts('user@stud', 'MD5-crypt', None)
    statreg('accounts', (time.time() - before))
    f = open('accounts.txt', 'wb', 16384)
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
        if acc.disk_path:
            f.write(acc.disk_path)
        f.write(':')
        if acc.disk_host:
            f.write(acc.disk_host)
        f.write(':')
        if acc.disk_host:
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
        if acc.owner_group_name:
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
        if ou.email:
            f.write(ou.email)
        f.write(':')
        if ou.url:
            f.write(ou.url)
        f.write(':')
        if ou.phone:
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
        if alias.server_name:
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
    ## homedirs = get_homedirs('not_created', 'mammut.stud.ntnu.no')
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

def test_changelogid():
    before = time.time()
    id = get_changelogid()
    statreg('changelogid',(time.time() - before))
    f = open('changelogid.txt', 'wb', 16384)
    str = '%d' % id
    f.write(str)
    f.flush()
    f.close()
    
def test_clients(count, verify=False, changelog=False, groups=False, accs=False, ous=False, aliases=False, homedirs=False, persons=False):
    set_username_password(cereconf.TEST_USERNAME, cereconf.TEST_PASSWORD)
    start_time = datetime.datetime.now()
    for i in range(count):
        if changelog:
            if verify:
                print >> sys.stderr, 'changelogid'
            test_changelogid()
        if groups:
            if verify:
                print >> sys.stderr, 'groups'
            test_groups()
        if accs:
            if verify:
                print >> sys.stderr, 'accounts'
            test_accounts()
        if ous:
            if verify:
                print >> sys.stderr, 'ous'
            test_ous()
        if aliases:
            if verify:
                print >> sys.stderr, 'aliases'
            test_aliases()
        if homedirs:
            if verify:
                print >> sys.stderr, 'homedirs'
            test_homedirs()
        if persons:
            if verify:
                print >> sys.stderr, 'persons'
            test_persons()
        if verify:
            print >> sys.stderr, 'Run: %d\n' % (i+1)
    statresult()
    end_time = datetime.datetime.now()
    print ''
    print 'Start time = ', start_time.strftime('%Y-%m-%d %H:%M:%S')
    print 'End time = ', end_time.strftime('%Y-%m-%d %H:%M:%S')
    print ''

    
def main():
    usage = "usage: %prog (-c COUNT | --count=COUNT) [-v|--verify] -lgaomdp"
    parser = OptionParser(usage)
    parser.add_option("-c", "--count", type="int", dest='count', help="number of runs")
    parser.add_option("-l", "--changelogid", action="store_true", dest='changelog', help="get logid")
    parser.add_option("-g", "--groups", action="store_true", dest='groups', help="get groups")
    parser.add_option("-a", "--accounts", action="store_true", dest='accs', help="get accounts")
    parser.add_option("-o", "--ous", action="store_true", dest='ous', help="get ous")
    parser.add_option("-m", "--mail", action="store_true", dest='aliases', help="get mail-aliases")
    parser.add_option("-d", "--dirs", action="store_true", dest='homedirs', help="get homedirs")
    parser.add_option("-p", "--persons", action="store_true", dest='persons', help="get persons")
    parser.add_option("-v", "--verify", action="store_true", dest='verify', help="show progress")
    
    (options, args) = parser.parse_args()
    if not options.count:
        parser.error("number of runs is 0 or not specified.")
    if options.count < 0:
        parser.error("number of runs cannot be less than 0.")
    if not options.changelog and not options.groups and not options.accs and not options.ous and not options.aliases and not options.homedirs and not options.persons:
        parser.print_help()
        parser.error("no test(s) is specified.")
    test_clients(options.count, verify=options.verify, changelog=options.changelog, groups=options.groups, accs=options.accs, ous=options.ous, aliases=options.aliases, homedirs=options.homedirs, persons=options.persons)
 
if __name__ == '__main__':
    main()
