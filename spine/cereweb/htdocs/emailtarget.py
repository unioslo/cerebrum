# -*- coding: iso-8859-1 -*-

# Copyright 2005 University of Oslo, Norway
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

import cherrypy
import sys
from gettext import gettext as _
from lib.Main import Main
from lib.utils import transaction_decorator, redirect, object_link
from lib.utils import commit, queue_message, legal_date
from lib.utils import legal_domain_format, legal_emailname, rollback_url
from SpineIDL.Errors import NotFoundError
from lib.templates.EmailTargetTemplate import EmailTargetTemplate
from lib.templates.EmailTargetViewTemplate import EmailTargetViewTemplate

def parse_address(address_obj):
    address = {
        'id': address_obj.get_id(),
        'local': address_obj.get_local_part(),
        'domain': address_obj.get_domain().get_name(),
        'created': address_obj.get_create_date().get_unix(),
        'changed': address_obj.get_change_date().get_unix(),
	'primary': address_obj.is_primary(),
    }
    expire = address_obj.get_expire_date()
    if expire:
        address['expire'] = expire.get_unix()
    else:
        address['expire'] = None
    return address

def parse_target(target_obj, t_id):
    try:
        name = target_obj.get_entity().get_name()
    except AttributeError, e:
        # There exists email targets without a target.
        # FIXME: Shouldn't happen, But for now we'll accept it.
        name = "None"

    target = {
        'id': t_id,
        'type': target_obj.get_type().get_name(),
        'entity': object_link(target_obj.get_entity()),
        'object_type': 'email_target',
	'name': "%s_email_target" % name,
    }

    try:
        primary_obj = target_obj.get_primary_address()
    except NotFoundError, e:
        primary_obj = None
    if primary_obj:
        target['primary'] = parse_address(primary_obj)
    else:
        target['primary'] = None
    for a in target_obj.get_addresses():
        target.setdefault('addresses', []).append(
            parse_address(a))
    return target

def view(transaction, id):
    id = int(id)
    target_obj = transaction.get_email_target(id)
    target = parse_target(target_obj, id)
    domains = transaction.get_email_domain_searcher().search()
    domains = [(i.get_name(), i.get_name()) for i in domains]
    page = Main()
    page.title = _("Email addresses")
    page.setFocus("/email", id)
    template = EmailTargetViewTemplate()
    content = template.view(target, domains)
    page.content = lambda: content
    return page
view = transaction_decorator(view)
view.exposed = True

def delete(transaction, id, ref):
    id = int(id)
    target_obj = transaction.get_email_target(id)
    addrs = target_obj.get_addresses()
    for adr in addrs:
        adr.delete()
    target_obj.delete_email_target()
    transaction.commit()
    redirect( ref )
delete = transaction_decorator(delete)
delete.exposed = True

def delete_addr(transaction, id, addr):
    addr = int(addr)
    addr = transaction.get_email_address(addr).delete()
    transaction.commit()
    queue_message('Email address successfully deleted.', error=False)
    redirect("/emailtarget/view?id=%s" % id)
delete_addr = transaction_decorator(delete_addr)
delete_addr.exposed = True

def edit(transaction, id):
    id = int(id)
    target = transaction.get_email_target(id)
    page = Main()
    page.title = _('Edit ') + object_link(target)
    page.setFocus('/emailtarget/edit', id)
    template = EmailTargetTemplate()
    content = template.edit_target(transaction,target)
    page.content = lambda: content
    return page
edit = transaction_decorator(edit)
edit.exposed = True

def makeaddress(transaction, id, local, domain, expire):
    id = int(id)
    target = transaction.get_email_target(id)
    msg = ''
    if local:
        if not legal_emailname(local):
            msg =_('Local is not a legal name.')
    else:
        msg = _('Local is empty.')

    # maybe commented in later as we have many test-domains
    # that do not have legal names.  tk.
    #if not msg:
    #    if domain:
    #        if not legal_domain_format(domain):
    #            msg = _('Domain is not a legal domain.')
    #    else:
    #        msg = _('Domain is empty.')

    if not msg:
        if expire:
            if not legal_date(expire):
                msg = _('Expire date is not a legal date.')
    if not msg:
        cmds = transaction.get_commands()
        domain = cmds.get_email_domain_by_name(domain)
        emailaddr = cmds.create_email_address(local, domain, target)
        if expire:
            expire = cmds.strptime(expire, "%Y-%m-%d")
            emailaddr.set_expire_date(expire)
        commit(transaction, target, msg=_("Email address successfully created."))
    else:
        rollback_url('/emailtarget/view?id=%s' % id, msg, err=True)
makeaddress = transaction_decorator(makeaddress)
makeaddress.exposed = True

def setprimary(transaction, id, addr):
    addr = transaction.get_email_address(int(addr))
    addr.set_as_primary()
    transaction.commit()
    queue_message('Email address successfully set as primary.', error=False)
    redirect("/emailtarget/view?id=%s" % id)
setprimary = transaction_decorator(setprimary)
setprimary.exposed = True

