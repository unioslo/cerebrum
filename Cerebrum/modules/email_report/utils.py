# -*- coding: utf-8 -*-
#
# Copyright 2020 University of Oslo, Norway
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
from __future__ import unicode_literals
import datetime

import jinja2

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from Cerebrum.Errors import NotFoundError


def write_html_report(template_name, template_path, codec, **kwargs):
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_path)
    )
    template = env.get_template(template_name)

    return template.render(encoding=codec.name, **kwargs).encode(codec.name)


def timestamp_title(title):
    iso_timestamp = datetime.datetime.now().strftime(' (%Y-%m-%d %H:%M:%S)')
    return title + iso_timestamp


def create_html_message(html,
                        plain_text,
                        codec,
                        subject=None,
                        from_addr=None,
                        to_addrs=None):
    message = MIMEMultipart('alternative')
    if subject:
        message['Subject'] = subject
    if from_addr:
        message['From'] = from_addr
    if to_addrs:
        message['To'] = to_addrs

    message.attach(MIMEText(plain_text, 'plain', codec.name))
    message.attach(MIMEText(html, 'html', codec.name))
    return message


def check_date(dates, today=None):
    """Check if today is one of the given dates"""
    if not dates:
        return True
    today = today or datetime.date.today()
    return (today.month, today.day) in [(d.month, d.day) for d in dates]


def get_account_email(const, account, account_id):
    account.clear()
    account.find(account_id)
    try:
        return account.get_primary_mailaddress()
    except NotFoundError:
        contact_info = account.get_contact_info(
            type=const.contact_email)
        if contact_info:
            return contact_info[0]['contact_value']
    return None


def count_members(gr, group_id):
    return len([m['member_id'] for m in gr.search_members(group_id=group_id)])


def get_account_name(account, account_id):
    account.clear()
    account.find(account_id)
    return account.account_name
