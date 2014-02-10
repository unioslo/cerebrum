#! /usr/bin/python
# -*- encoding: utf-8 -*-
#
# $Id$
#
# $Date: 2009-05-08 14:11:12 +0200 (Fri, 08 May 2009) $
#
import re
import sys
import cookielib
import urllib2
import urllib
import time
import math
import getpass
import datetime

cj = cookielib.CookieJar()
opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))

stat_max_min = {}

## MODE = "test"
MODE = "utvikling"

username="bootstrap_account"

password= sys.argv[1]
if MODE == "test":
   server = "https://ceretest.itea.ntnu.no"
   idmap = {
       'ss_bdb' : 232,
       'ss_manual' : 231,
       'ansatt': 30,
       'nits': 3625,
       'vitp': 3619,
       'hmvi': 3707,
       'svill': 3840,
       'nall': 205268,
       'bertelli': 70852,
       'kandal': 131216,
       'bertil': 72278,
       'stigst': 53462,
       'geirha': 82369,
       'bjorbert': 54552,
       'grabczyn': 308508,
       'arneve': 131211,
       'persverr': 131404,
       'trond_kandal': 7146,
       'kyrre_myrbostad': 5419,
       'janne_hanssen': 41265,
       'bjorn_bertheussen': 50125,
       'morten_abildsnes': 13946,
       'trond_abusdal': 103592,
       'kristin_agersen': 17029,
       'oi-stab': 51091,
       'ime': 51073,
       'ivt-ipm': 51157,
       'ivt': 51067,
       'ivt-adm': 207675,
       're': 51062,
       'oe': 51069,
       'jak': 3536,
       'homep': 3545,
       'homes': 3550,
       'homeo': 3544,
       'homet': 3551,
       'homeq': 3547,
       'homer': 3548,
       'fim': 3559,
       'imm': 3563,
       'kkt': 3570,
       'maskin': 3573,
       'medisin': 3575,
       'stud': 3583,
       'ansatt_ansatt': 34,
       'ansatt_tekadm': 44,
   }
elif MODE == "utvikling":
   server="http://ceredev.itea.ntnu.no:8081"
   idmap = {
       'ss_bdb' : 16,
       'ss_manual' : 15,
       'ansatt' : 94,
       'nits': 149,
       'vitp': 143,
       'hmvi': 231,
       'svill': 363,
       'nall': 288,
       'bertelli': 122229,
       'kandal': 173688,
       'bertil': 122229,
       'stigst': 107775,
       'geirha': 132420,
       'bjorbert': 108857,
       'grabczyn': 292101,
       'arneve': 173683,
       'persverr': 173862,
       'trond_kandal': 3691,
       'kyrre_myrbostad': 1952,
       'janne_hanssen': 37895,
       'bjorn_bertheussen': 37399,
       'morten_abildsnes': 10510,
       'trond_abusdal': 52574,
       'kristin_agersen': 13598,
       'oi-stab': 33,
       'ime': 15,
       'ivt-ipm': 99,
       'ivt': 9,
       'ivt-adm': 38,
       're': 4,
       'oe': 11,
       'jak': 346781,
       'homep': 346790,
       'homes': 346793,
       'homeo': 346789,
       'homet': 346794,
       'homeq': 346791,
       'homer': 346792,
       'fim':  212122,
       'imm': 212130,
       'kkt': 212140,
       'maskin': 212143,
       'medisin': 212145,
       'stud': 212158,
       'ansatt_ansatt': 98,
       'ansatt_tekadm': 108,
   }

rresult = re.compile(r'<!-- RESULT: (.*?)-->')

def getpage(page, post=None):
  req = urllib2.Request(server + page)
  if post:
      req.add_data(urllib.urlencode(post))
  r = opener.open(req)
  data = r.read()
  print data
  match = rresult.search(data)
  return match and match.group(1) or "No result returned."

samples={}
def statreg(stat, t):
  if not stat in samples:
      samples[stat]=(0, 0.0, 0.0)
  n, sum, ssum = samples[stat]
  if not stat_max_min.get(stat):
     stat_max_min[stat] = []
  stat_max_min[stat].append(t)
  samples[stat]=(n+1, sum+t, ssum+t*t)

def statresult():
  print '%-19s  %s\t%s\t\t%s\t\t%s\t\t%s' % ('Operation',
                                            'Average',
                                            'Varying',
                                            'Max',
                                            'Min',
                                            'Runs')
  print '------------------------------------------------------------------------------------'
  for k,v in samples.items():
      n, sum, ssum = v
      mean=sum/n
      sd=math.sqrt(ssum/n-mean*mean)
      print "%-19s: %2.6f\t~%2.6f\t%2.6f\t%2.6f\t%d" % (k, mean,
                                                           sd,
                                                           max(stat_max_min[k]),
                                                           min(stat_max_min[k]),
                                                           n) 
  print ''

def statreset():
  samples.clear()

def stdout_write(str):
  sys.stdout.write(str)

def tgetpage(stat, page, post=None):
  start=time.time()
  result = getpage(page, post)
  end=time.time()
  statreg(stat, (end-start))
  print "Time: %f" % (end-start)
  print "Result: %s" % result

def run_login(post=None):
  sys.stdout.write('Login ')
  tgetpage("login", "/login", post)

def run_logout(post=None):
  sys.stdout.write('Logout ')
  tgetpage("logout", "/logout")

def run_pers_search(post=None):
  str = 'Person search = %s - ' % post
  sys.stdout.write(str)
  tgetpage('person_search','/search/person', post)

def run_pers_view(post=None):
  str = 'Person view = %s - ' % post
  sys.stdout.write(str)
  tgetpage("person_view", '/person/view?id=%s' % (post))

def run_pers_save(page, post=None):
  str = 'Person save = %s - ' % post
  sys.stdout.write(str)
  tgetpage('pers_' + page, '/person/' + page, post)

def run_acc_search(post=None):
  str = 'Account search = %s - ' % post
  sys.stdout.write(str)
  tgetpage("acc_search", "/search/account", post)

def run_acc_view(post=None):
  str = 'Account view  =  %s - ' % post
  sys.stdout.write(str)
  tgetpage("acc_view", "/account/view?id=%s" %(post))

def run_acc_save(page, post=None):
  str = 'Account save = %s - ' % post
  sys.stdout.write(str)
  tgetpage('acc_' + page, '/account/' + page, post)

def run_group_search(post=None):
  str = 'Group search = %s - ' % post
  sys.stdout.write(str)
  tgetpage('group_search', '/search/group', post)

def run_group_view(post=None):
  str = 'Group view %s - ' % post
  sys.stdout.write(str)
  tgetpage('group_view', '/group/view?id=%s' % (post))

## def run_ou_search(post=None):
##   str='OU search %s - ' % post
##   sys.stdout.write(str)
##   tgetpage('ou_search', '/search/ou', post)

def run_ou_view(post=None):
  str = 'OU view %s - ' % post
  sys.stdout.write(str)
  tgetpage('ou_view', '/ou/view?id=%s' % (post))

def run_host_search(post=None):
   str = 'Host search = %s - ' % post
   sys.stdout.write(str)
   tgetpage('host_search', '/search/host', post)

def run_host_view(post=None):
   str = 'Host view = %s - ' % post
   sys.stdout.write(str)
   tgetpage('host_view', '/host/view?id=%s' % (post))

def run_disk_search(post=None):
  str = 'Disk search = %s - ' % post
  sys.stdout.write(str)
  tgetpage('disk_search', '/search/disk', post)

def run_disk_view(post=None):
  str = 'Disk view = %s - ' % post
  sys.stdout.write(str)
  tgetpage('disk_view', '/disk/view?id=%s' % (post))

## def run_email_search(post=None):
  ## str = 'Email search = %s - ' % post
  ## sys.stdout.write(str)
  ## tgetpage('email_search', '/email/search', post)

def run_email_view(post=None):
    str = 'Email view = %s - ' % post
    sys.stdout.write(str)
    tgetpage('email_view', '/email/view?id=%s' % (post))


pass

person_search = (
     {'name' : '*hanssen*'},
     {'accountname' : 'fjerdrum'},
     {'birthdate' : '1978-06-23'},
     {'ou' : '*fakultet*matematikk*'},
     {'aff' : '*ansatt*'},
     {'accountname' : 'persverr'},
     )

person_view = (
     idmap['janne_hanssen'],
     idmap['kyrre_myrbostad'],
     idmap['bjorn_bertheussen'],
     idmap['morten_abildsnes'],
     idmap['trond_abusdal'],
     idmap['kristin_agersen'],
     )

person_add_name = ( 
  {'id' : idmap['trond_kandal'], 'name' : 'shemale', 'name_type' : 'PERSONALTITLE'},
  {'id' : idmap['trond_kandal'], 'name' : 'cuckoo', 'name_type' : 'WORKTITLE'},
  {'id' : idmap['trond_kandal'], 'name' : 'shemale', 'name_type' : 'PERSONALTITLE'},
  )

person_add_affil = (
  {'id' : idmap['trond_kandal'], 'status' : idmap['ansatt_tekadm'], 'ou' : idmap['ivt-adm']},
  {'id' : idmap['trond_kandal'], 'status' : idmap['ansatt_ansatt'], 'ou' : idmap['oi-stab']},
  {'id' : idmap['trond_kandal'], 'status' : idmap['ansatt_tekadm'], 'ou' : idmap['ivt-ipm']},
  )

person_rm_affil = (
    {'id' : idmap['trond_kandal'], 'ou' : idmap['ivt-adm'], 'affil' : idmap['ansatt_tekadm'], 'ss' : idmap['ss_manual']},
    {'id' : idmap['trond_kandal'], 'ou' : idmap['oi-stab'], 'affil' : idmap['ansatt_ansatt'], 'ss' : idmap['ss_manual']},
    {'id' : idmap['trond_kandal'], 'ou' : idmap['ivt-ipm'], 'affil' : idmap['ansatt_tekadm'], 'ss' : idmap['ss_manual']},
)

account_search = (
  {'name' : 's*ant'},
  {'name': 'st*n*'},
  {'name' : '*bert*'},
  {'create_date': '2008-10-10'},
  {'expire_date': '2008-10-10'},
  {'name': 'laa'},
  )

account_view = (
   idmap['stigst'],
   idmap['geirha'],
   idmap['bjorbert'],
   idmap['grabczyn'],
   idmap['arneve'],
   idmap['persverr'],
)


account_add_affil = (
  {'account_id' : idmap['kandal'], 'aff_ou' : '%d:%s' % (idmap['ansatt'], idmap['ivt-adm']), 'priority' : '300'},
  {'account_id' : idmap['kandal'],'aff_ou' : '%d:%s' % (idmap['ansatt'], idmap['oi-stab']), 'priority' : '400'},
  )

##  {'account_id' : idmap['kandal'], 'aff_ou' : '%d:%s' % (idmap['ansatt'], idmap['ivt-adm']), 'priority' : '500'},

account_rm_affil = (
    {'account_id' : idmap['kandal'], 'ou_id' : idmap['ivt-adm'], 'affil_id' : idmap['ansatt']},
    {'account_id' : idmap['kandal'], 'ou_id' : idmap['oi-stab'], 'affil_id' : idmap['ansatt']},
)

## {'account_id' : idmap['kandal'], 'ou_id' : idmap['ivt-adm'], 'affil_id' : idmap['ansatt_tekadm']},

account_add_spread = (
  {'id' : idmap['bertelli'], 'spread': 'user@kybernetikk'},
  {'id' : idmap['bertelli'], 'spread': 'user@ivt'},
  {'id' : idmap['bertelli'], 'spread': 'user@math'},
  )

account_rm_spread = (
  {'id' : idmap['bertelli'], 'spread' : 'user@kybernetikk'},
  {'id' : idmap['bertelli'], 'spread': 'user@ivt'},
  {'id' : idmap['bertelli'], 'spread': 'user@math'},

)

group_search = (
  {'name' : 'nit*'},
  {'description' : 'IT-seksjonen'},
  {'name' : 'ssa*'},
  {'description' : 'SVT*Institutt for sosialøkonomi'},
  {'name' : 'vall'},
  {'description': 'VM*Botanisk avdeling'},
  {'name' : '*oma'},
  {'description' : 'Personalseksjonen'},
  )

group_view = (
   idmap['nits'],
   idmap['vitp'],
   idmap['hmvi'],
   idmap['svill'],
   idmap['nall'],
  )

group_add_spread = (
  {'id' : idmap['nits'], 'spread' : 'netgroup@ntnu'},
)

group_rm_spread = (
    {'id' : idmap['nits'], 'spread' : 'netgroup@ntnu'},
)

group_add_member = (
  {'group_id' : idmap['nits'], 'member_name' : 'bertelli', 'member_type' : 'account'},
  {'group_id' : idmap['nits'], 'member_name' : 'bertil', 'member_type' : 'account'},
)

group_rm_member = (
  {'group_id' : idmap['nits'], 'member_id' : idmap['bertelli']},
  {'group_id' : idmap['nits'], 'member_id' : idmap['bertil']},
  )

ou_search = (
  {'name' : '*fakultet*matematikk*'},
  {'name' : '*institutt*matemati*'},
  {'name' : '*institutt*produkt*'},
  {'acronym' : 'SVT'},
  {'acronym' : 'IME'},
  {'acronym' : 'IVT-IPD'},
)

ou_view = (
   idmap['ime'],
   idmap['ivt-ipm'],
   idmap['ivt'],
   idmap['ivt-adm'],
   idmap['re'],
   idmap['oe'],
)

host_search = (
  {'name': '*'},
  {'description': '*stud*'},
  {'name' : '*itea*'},
  {'description' : '*ansatte*'},
  {'name' : 'jak.itea.ntnu.no'},
  {'description' : '*homeserver*'},
  )

host_view = (
   idmap['jak'],
   idmap['jak'],
   idmap['jak'],
   idmap['jak'],
  )

disk_search = (
  {'path' : '*'},
  {'description' : '*'},
  {'path' : '/home/homeo'},
  {'path' : '*home/homep*'},
  {'path' : '/home*'},
  {'path' : '/home/ahomea*'},
  )

disk_view = (
   idmap['homep'],
   idmap['homes'],
   idmap['homeo'],
   idmap['homet'],
   idmap['homeq'],
   idmap['homer'],
  )

email_search = (
  {'name' : '*bygde*'},
  {'description' : '*BDB*'},
  {'name' : '*ark*'},
  {'description' : '*'},
  {'name' : '*'},
  {'description' : '*imported*'},
  )

email_view = (
   idmap['fim'],
   idmap['imm'],
   idmap['kkt'],
   idmap['maskin'],
   idmap['medisin'],
   idmap['stud'],
  )

statreset()
start_time = datetime.datetime.now()
for i in range(20):
  cj = cookielib.CookieJar()
  opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
  print 'Run number: %d' % (i + 1)
  run_login({'username': username,
            'password': password,
            'client': '/index' })

  ## 
  ## add a name for person
  ## finished...
  for ps in person_add_name:
    run_pers_save('add_name', ps)

  ## finished
  ## add an affiliation for person.
  for pa in person_add_affil:
    run_pers_save('add_affil', pa)


  ## add an affiliation for account
  ## finished...
  for aa in account_add_affil:
    run_acc_save('add_affil', aa)

  ## finished ...
  for ad in account_rm_affil:
    run_acc_save('remove_affil', ad)

  ## finished
  for pd in person_rm_affil:
    run_pers_save('remove_affil', pd)

## Disabled until we've converted entity
#   ## remove spreads before adding, or else
#   ## the db will complain about already extisting.
  for i in range(2):
    for aas in account_add_spread:
      stdout_write('Account remove = %s - ' % aas)
      tgetpage('acc_rm_spread', '/entity/remove_spread', aas)
      time.sleep(1)
      stdout_write('Account save = %s - ' % aas)   
      tgetpage('acc_add_spread', '/entity/add_spread', aas)
      time.sleep(1)

## Disabled until we've converted entity
  for i in range(3):
    for gs in group_add_spread:
      stdout_write('Group remove = %s - ' % gs)
      tgetpage('grp_rm_spread', '/entity/remove_spread', gs)
      time.sleep(1)
      stdout_write('Group save = %s - ' % gs)
      tgetpage('grp_add_spread', '/entity/add_spread', gs)
      time.sleep(1)

  ## finished...
  for i in range(1):
    for ga in group_add_member:
      stdout_write('Group save = %s - ' % ga)
      tgetpage('grp_add_mem', '/group/add_member', ga)
    time.sleep(1)
    for gr in group_rm_member:
      stdout_write('Group remove = %s - ' % gr)
      tgetpage('grp_rm_mem', '/group/remove_member', gr)
    time.sleep(1)

## Disabled until we've converted the searcher.
  for acc in account_search:
    for k,v in acc.iteritems():
        print 'account value = ', v
        stdout_write('Account search = %s - ' % v)
        url = '/search/account?%s=%s' % (k, urllib.quote(v))
        tgetpage('acc_search', url )
        #run_acc_search(a)

  ## finsihed...
  for a in account_view:
    run_acc_view(a)

## Disabled until we've converted the searcher.
  for pp in person_search:
    for k,v in pp.iteritems():
        stdout_write('Person search = %s' % v)
        str = '/search/person?%s=%s' %(k, urllib.quote(v))
        tgetpage('pers_search',str)
        ## run_pers_search(p)

  ## finished
  for p in person_view:
    run_pers_view(p)

## Disabled until we've converted the searcher.
# 
  for grp in group_search:
    for k,v in grp.iteritems():
        stdout_write('Group search = %s -' % v)
        url = '/search/group?%s=%s' % (k, urllib.quote(v))
        tgetpage('grp_search', url)
        ##run_group_search(g)

  ## finished...
  for g in group_view:
    run_group_view(g)

## Disabled until we've converted the searcher.
##  for ous in ou_search:
##    for k,v in ous.iteritems():
##        stdout_write('OU search = %s - ' % v)
##        url = '/search/ou?%s=%s' % (k, urllib.quote(v))
##        tgetpage('ou_search', url)
        ## run_ou_search(o)

## Disabled until we've converted ou
  for o in ou_view:
    run_ou_view(o)

## Disabled until we've converted the searcher.
  for host in host_search:
    for k, v in host.iteritems():
        stdout_write('Host search = %s - ' % v)
        url = '/search/host?%s=%s' % (k, urllib.quote(v))
        tgetpage('host_search', url)
        ## run_host_search(h)

## Disabled until we've converted host
  for h in host_view:
    run_host_view(h)

## Disabled until we've converted the searcher.
  for disk in disk_search:
    for k,v in disk.iteritems():
        stdout_write('Disk search = %s - ' % v)
        url = '/search/disk?%s=%s' % (k, urllib.quote(v))
        tgetpage('disk_search', url)
        ## run_disk_search(d)

## Disabled until we've converted disk
  for d in disk_view:
    run_disk_view(d)

## Disabled until we've converted the searcher.
##  for email in email_search:
##    for k,v in email.iteritems():
##        stdout_write('Email search = %s - ' % v)
##        url = '/search/email?%s=%s' % (k, urllib.quote(v))
##        tgetpage('email_search', url)
        ## run_email_search(e)

## Disabled until we've converted email
  for e in email_view:
    run_email_view(e)

  run_logout()
  sys.stdout.write('\n\n')
  time.sleep(2)

end_time = datetime.datetime.now()
statresult()

print ''
print 'Start time = ', start_time.strftime('%Y-%m-%d %H:%M:%S')
print 'End time = ', end_time.strftime('%Y-%m-%d %H:%M:%S')
print ''

