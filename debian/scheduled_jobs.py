# -*- coding: iso-8859-1 -*-
# $Id$

# This is an example of scheduling settings that can be used in a
# cerebrum installation.  See the documentation for job_runner for
# details.

from job_actions import *
from job_utils import When, Time

def get_jobs():
    sbin = '/cerebrum/sbin'
    contrib = '/cerebrum/share/cerebrum/contrib'
    feidegvscontrib = contrib + '/no/feidegvs'
    dumpdir = '/cerebrum/dumps'
    ldapdir = dumpdir + '/LDAP'
    return {
        'backup': Action(call=System('%s/backup.py' % sbin),
                         max_freq=23*60*60),
        'rotate_logs': Action(call=System('%s/rotate_logs.py' % sbin),
                              max_freq=23*60*60),
        'ldif_user':
          Action(call=System('%s/generate_user_ldif.py' % feidegvscontrib,
                             params=['--file', '%s/users-db.ldif' % ldapdir]),
                 max_freq=60*60),
        'ldif_mail':
            Action(call=System('%s/generate_mail_ldif.py' % feidegvscontrib,
                               params=['-m', '%s/mail-db.ldif' % ldapdir]),
                   max_freq=60*60, when=When(freq=90*60))
        }

