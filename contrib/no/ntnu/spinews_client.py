import sys, os, re, time

import cerebrum_path
for pp in sys.path:
    print pp

from SignatureHandler import *
from Cerebrum.lib.spinews.spinews_services import *
from Cerebrum.lib.spinews.spinews_services_types import *
from ZSI.ServiceContainer import ServiceSOAPBinding

kw = {'tracefile' : sys.stdout}

def get_ceresync_port():
    locator = spinewsLocator()
    return locator.getspinePortType(**kw)

def sign_request(username, password, port):
    sigHandler = SignatureHandler(username, password, False)
    port.binding.sig_handler = sigHandler
 
def get_groups(username, password, groupspread, accountspread, inc_from=None):
    port = get_ceresync_port()
    sign_request(username, password, port)
    request = getGroupsRequest()
    request._groupspread = groupspread
    request._accountspread = accountspread
    request._incremental_from = inc_from
    return port.get_groups(request)

def get_accounts(username, password, accountspread, inc_from=None):
    port = get_ceresync_port()
    sign_request(username, password, port)
    request = getAccountsRequest()
    request._accountspread = accountspread
    request._incremental_from = inc_from
    return port.get_accounts(request)
 
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
    print ""

before = time.time()
response = get_accounts('hjalla', 'gork', 'user@ansatt', None)
print "Get accounts time: %f" % (time.time() - before)
for acc in response._account:
    quarantines = acc._quarantine
    for k in acc.attrs.keys():
        print '%s: %s' % (k, acc._attrs.get(k, ''))
    
