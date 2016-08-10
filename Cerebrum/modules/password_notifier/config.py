# -*- coding: utf-8 -*-

# Copyright 2016 University of Oslo, Norway
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
"""This module defines all necessary config for the password notifier module"""

from Cerebrum.modules.PasswordNotifierConstants import Constants as PNConstants
from Cerebrum.config.configuration import (ConfigDescriptor,
                                           Configuration,
                                           Namespace)
from Cerebrum.config.loader import read, read_config
from Cerebrum.config.settings import (Boolean,
                                      Integer,
                                      String,
                                      Iterable,
                                      NotSet)


class AffiliationBasedValue(Configuration):
    """
    """
    affiliation = ConfigDescriptor(
        String,
        minlen=1,
        doc=u'The affiliation string')

    max_password_age = ConfigDescriptor(
        Integer,
        default=365,
        minval=1,
        doc=u'The maximum age of a password in days for this affiliation')

    warn_before_expiration_days = ConfigDescriptor(
        Integer,
        default=2*7,
        minval=1,
        doc=(u'How many days before password expiration do we send '
             'notification for this affiliation'))


class PasswordNotifierConfig(Configuration):
    """
    """
    change_log_program = ConfigDescriptor(
        String,
        default='notify_ch_passwd',
        doc=u'Change program')

    change_log_account = ConfigDescriptor(
        String,
        default='',
        doc=u'Change account')

    templates = ConfigDescriptor(
        Iterable,
        template=String(),
        default=[],
        doc=u'Templates')

    max_password_age = ConfigDescriptor(
        Integer,
        default=365,
        minval=1,
        doc=u'The maximum age of a password in days')
        
    max_new_notifications = ConfigDescriptor(
        Integer,
        default=0,
        minval=0,
        doc=u'The maximum amount of new notifications')

    grace_period = ConfigDescriptor(
        Integer,
        default=35,
        minval=1,
        doc=u'The grace period in days')

    reminder_delay_values = ConfigDescriptor(
        Iterable,
        template=Integer(minval=1),
        default=[14],
        doc=u'A list of reminder delay values')

    class_notifier_values = ConfigDescriptor(
        Iterable,
        template=String(),
        default=['Cerebrum.modules.PasswordNotifier/PasswordNotifier'],
        doc=u'A list of notification classes')

    trait = ConfigDescriptor(
        Setting,
        default=PNConstants.trait_passwordnotifier_notifications,
        doc=u'The trait to be set for notification')

    except_trait = ConfigDescriptor(
        Setting,
        default=PNConstants.trait_passwordnotifier_excepted,
        doc=u'The trait used to prevent notification')

    summary_from = ConfigDescriptor(
        String,
        default='',
        doc=u'The email to send notification summary from')

    summary_to = ConfigDescriptor(
        Iterable,
        template=String(),
        default=[],
        doc=u'The email(s) to send notification summary to')

    summary_cc = ConfigDescriptor(
        Iterable,
        template=String(),
        default=[],
        doc=u'The CC email(s) to send notification summary to')

    summary_bcc = ConfigDescriptor(
        Iterable,
        template=String(),
        default=[],
        doc=u'The BCC email(s) to send notification summary to')

    affiliation_mappings = ConfigDescriptor(
        Iterable,
        template=AffiliationBasedValue(),
        default=[],
        doc=u'The affiliation mappings')
