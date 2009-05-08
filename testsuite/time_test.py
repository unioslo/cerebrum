#! /usr/bin/python
# -*- encoding: utf-8 -*-
#
# $Id$
#
# $Date$
#
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

server="https://ceretest.itea.ntnu.no"

def getpage(page, post=None):
   req = urllib2.Request(server + page)
   if post:
       req.add_data(urllib.urlencode(post))
   r = opener.open(req)
   for h,v in r.headers.items():
      line = "%s: %s\n" % (h,v)
      sys.stderr.write(line)
   sys.stderr.write(r.read())


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
   print '%-15s  %s\t%s\t\t%s\t\t%s\t\t%s' % ('Operation',
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
       print "%-15s: %2.6f\t~%2.6f\t%2.6f\t%2.6f\t%d" % (k, mean,
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
   getpage(page, post)
   end=time.time()
   statreg(stat, (end-start))
   print "Time: %f" % (end-start)

def run_login(post=None):
   sys.stdout.write('Login ')
   tgetpage("login", "/login", post)

def run_logout(post=None):
   sys.stdout.write('Logout ')
   tgetpage("logout", "/logout")

def run_pers_search(post=None):
   str = 'Person search = %s - ' % post
   sys.stdout.write(str)
   tgetpage('person_search','/person/search', post)

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
   tgetpage("acc_search", "/account/search", post)

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
   tgetpage('group_search', '/group/search', post)

def run_group_view(post=None):
   str = 'Group view %s - ' % post
   sys.stdout.write(str)
   tgetpage('group_view', '/group/view?id=%s' % (post))

def run_ou_search(post=None):
   str='OU search %s - ' % post
   sys.stdout.write(str)
   tgetpage('ou_search', '/ou/search', post)

def run_ou_view(post=None):
   str = 'OU view %s - ' % post
   sys.stdout.write(str)
   tgetpage('ou_view', '/ou/view?id=%s' % (post))

def run_host_search(post=None):
    str = 'Host search = %s - ' % post
    sys.stdout.write(str)
    tgetpage('host_search', '/host/search', post)

def run_host_view(post=None):
    str = 'Host view = %s - ' % post
    sys.stdout.write(str)
    tgetpage('host_view', '/host/view?id=%s' % (post))

def run_disk_search(post=None):
   str = 'Disk search = %s - ' % post
   sys.stdout.write(str)
   tgetpage('disk_search', '/disk/search', post)

def run_disk_view(post=None):
   str = 'Disk view = %s - ' % post
   sys.stdout.write(str)
   tgetpage('disk_view', '/disk/view?id=%s' % (post))

def run_email_search(post=None):
   str = 'Email search = %s - ' % post
   sys.stdout.write(str)
   tgetpage('email_search', '/email/search', post)

def run_email_view(post=None):
   str = 'Email view = %s - ' % post
   sys.stdout.write(str)
   tgetpage('email_view', '/email/view?id=%s' % (post))


pass

sys.stdout.write('username: ')
username=raw_input('')
password=getpass.getpass("password: ")
print ''

person_search = (
      {'name' : '*hanssen*'},
      {'accountname' : 'fjerdrum'},
      {'birthdate' : '1978-06-23'},
      {'ou' : '*fakultet*matematikk*'},
      {'aff' : '*ansatt*'},
      {'accountname' : 'persverr'},
      )

person_view = (
      '41265',
      '5419',
      '50125',
      '13946',
      '103592',
      '17029',
      )

person_add_name = ( 
   {'id' : 7146, 'name' : 'shemale', 'name_type' : 'PERSONALTITLE'},
   {'id' : 7146, 'name' : 'cuckoo', 'name_type' : 'WORKTITLE'},
   {'id' : 7146, 'name' : 'shemale', 'name_type' : 'PERSONALTITLE'},
   )

person_add_affil = (
   {'id' : 7146, 'status' : 44, 'ou' : 51096},
   {'id' : 7146, 'status' : 34, 'ou' : 51091},
   {'id' : 7146, 'status' : 44, 'ou' : 51096},
   )

account_search = (
   {'name' : 's*'},
   {'name': 'st*n*'},
   {'name' : '*bert*'},
   {'create_date': '2008-10-10'},
   {'expire_date': '2008-10-10'},
   {'name': 'laa'},
   )

account_view = (
      '53462',
      '82369',
      '54552',
      '308508',
      '131211',
      '131404',
      )


account_add_affil = (
   {'id' : 131216, 'aff_ou' : 'ANSATT:51096', 'priority' : '300'},
   {'id' : 131216, 'aff_ou' : 'ANSATT:51091', 'priority' : '400'},
   {'id' : 131216, 'aff_ou' : 'ANSATT:51096', 'priority' : '300'},
   )

account_add_spread = (
   {'id' : 131216, 'spread': 'user@kybernetikk'},
   {'id' : 131216, 'spread': 'user@ivt'},
   {'id' : 131216, 'spread': 'user@math'},
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
   '3625',
   '3619',
   '3707',
   '3840',
   '3625',
   '205268',
   )

group_add_spread = (
   {'id' : 3625, 'spread' : 'netgroup@ntnu'},
)

group_add_member = (
   {'id' : 3625, 'name' : 'bertelli', 'type' : 'account'},
   {'id' : 3625, 'name' : 'bertil', 'type' : 'account'},
   )

group_rm_member = (
   {'groupid' : 3625, 'memberid' : 70852},
   {'groupid' : 3625, 'memberid' : 72278},
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
      '51073',
      '51157',
      '51067',
      '207675',
      '51062',
      '51069',
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
   '3536',
   '3546',
   '3543',
   '3549',
   '3536',
   '3543',
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
   '3545',
   '3550',
   '3544',
   '3551',
   '3547',
   '3548',
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
   '3559',
   '3563',
   '3570',
   '3573',
   '3575',
   '3583',
   )

statreset()
start_time = datetime.datetime.now()
for i in range(50):
   print 'Run number: %d' % (i + 1)
   run_login({'username': username,
             'password': password,
             'client': '/index' })

   ## add a name for person
   for ps in person_add_name:
      run_pers_save('add_name', ps)

   ## add an affiliation for person.
   for pa in person_add_affil:
      run_pers_save('add_affil', pa)

   ## add an affiliation for account
   for aa in account_add_affil:
      run_acc_save('add_affil', aa)


## remove spreads before adding, or else
## the db will complain about already extisting.
   for i in range(2):
      for as in account_add_spread:
         stdout_write('Account remove = %s - ' % as)
         tgetpage('acc_rm_spread', '/entity/remove_spread', as)
         time.sleep(1)
         stdout_write('Account save = %s - ' % as)   
         tgetpage('acc_add_spread', '/entity/add_spread', as)
         time.sleep(1)

   for i in range(3):
      for gs in group_add_spread:
         stdout_write('Group remove = %s - ' % gs)
         tgetpage('grp_rm_spread', '/entity/remove_spread', gs)
         time.sleep(1)
         stdout_write('Group save = %s - ' % gs)
         tgetpage('grp_add_spread', '/entity/add_spread', gs)
         time.sleep(1)

   for i in range(3):
      for ga in group_add_member:
         stdout_write('Group save = %s - ' % ga)
         tgetpage('grp_add_mem', '/group/add_member', ga)
      time.sleep(1)
      for gr in group_rm_member:
         stdout_write('Group remove = %s - ' % gr)
         tgetpage('grp_rm_mem', '/group/remove_member', gr)
      time.sleep(1)

   for a in account_search:
      run_acc_search(a)
 
   for a in account_view:
      run_acc_view(a)
 
   for p in person_search:
      run_pers_search(p)
 
   for p in person_view:
      run_pers_view(p)
 
   for g in group_search:
      run_group_search(g)
    
   for g in group_view:
      run_group_view(g)
 
   for o in ou_search:
      run_ou_search(o)
 
   for o in ou_view:
      run_ou_view(o)
 
   for h in host_search:
      run_host_search(h)
 
   for h in host_view:
      run_host_view(h)
      
   for d in disk_search:
      run_disk_search(d)
 
   for d in disk_view:
      run_disk_view(d)
 
   for e in email_search:
      run_email_search(e)
 
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
