#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
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

# Clean out manually registered affiliation if an equivalent affiliation
# has been registered by an authoritative system.


import cerebrum_path
from Cerebrum import Utils, Errors
import cereconf
import string
import mx.DateTime
from string import Template
import smtplib

Factory = Utils.Factory
db = Factory.get('Database')()
co = Factory.get('Constants')(db)
account = Factory.get("Account")(db)
person = Factory.get("Person")(db)
logger = Factory.get_logger("cronjob")

from Cerebrum.modules import Email
emailtarget = Email.EmailPrimaryAddressTarget(db)

def warn_users(fromdate, todate, template, smtp_server, bounce_address):
    s = smtplib.SMTP(smtp_server)
    for a in account.search(expire_start=fromdate, expire_stop=todate):
        emailtarget.clear()
        addr = None
        address = None
        try:
            emailtarget.find_by_target_entity(a['account_id'])
        except Errors.NotFoundError:
            pass
        else:
            for addr in emailtarget.get_addresses():
                if addr['address_id'] == emailtarget.email_primaddr_id:
                    break
        if addr:
            address = addr['local_part'] + '@' + addr['domain']
        else:
            for c in person.list_contact_info(entity_id = a['owner_id'],
                                              contact_type = co.contact_email):
                address = c['contact_value']

        if not address:
            logger.warn("Account %s will expire, but could not inform user:"+
                        " has no email address.",
                        a['name'])
            continue

        expire_date = mx.DateTime.DateFrom(a['expire_date'])
        expire_days = (mx.DateTime.now() - expire_date).days

        mapping = {
            'expire_days': str(int(expire_days + 0.5)),
            'expire_date': expire_date.Format("%Y-%m-%d"),
            'accountname': a['name'],
            'address': address,
            }

        mailtext = template.safe_substitute(mapping)
        s.sendmail(bounce_address, [address], mailtext)
        logger.info("Account %s will expire, warned by email to %s",
                    a['name'], address)
    s.quit()

def main():
    try:
        days = cereconf.MAIL_EXPIRE_ACCOUNTS_DAYSBEFORE
    except AttributeError:
        days = 14

    try:
        lastfile = cereconf.MAIL_EXPIRE_ACCOUNTS_TIMESTAMP
    except AttributeError:
        lastfile = '/var/log/cerebrum/mail_expire_accounts.timestamp'

    now = mx.DateTime.now()
    warntime = now - days
    try:
        last = mx.DateTime.DateFrom(open(lastfile).read())
    except IOError:
        last = warntime - 1 # Assume daily

    try:
        template = cereconf.MAIL_EXPIRE_ACCOUNTS_TEMPLATE
    except AttributeError:
        template = '/etc/cerebrum/mail_expire_accounts.template'

    try:
        bounce_address = cereconf.MAIL_EXPIRE_ACCOUNTS_BOUNCE
    except AttributeError:
        bounce_address = "devnull@ntnu.no"

    try:
        smtp_server = cereconf.SMTP_SERVER
    except AttributeError:
        smtp_server = "localhost"

    template = Template(open(template).read())

    warn_users(last, warntime, template, smtp_server, bounce_address)
    
    f = open(lastfile, 'w')
    f.write(str(warntime))
    f.close()

if __name__ == '__main__':
    main()
