#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2008-2015 University of Oslo, Norway
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

import mx.DateTime as dt
import getopt
import sys

import cerebrum_path
import cereconf

from Cerebrum import Utils
from Cerebrum.modules.PasswordNotifier import PasswordNotifier

import changepassconf as config

logger = Utils.Factory.get_logger("cronjob")
db = Utils.Factory.get('Database')()
co = Utils.Factory.get('Constants')(db)


def main():
    try:
        opts, args = getopt.getopt(
            sys.argv[1:],
            'ph',
            [
            'help',   # prints usage and exits successfully
            'debug',  # enables debug-mode: no side effects
            'to=',    # to address for status-mail
            'cc=',    # cc address for status-mail
            'bcc=',   # bcc address for status-mail
            'from=',  # from address for status-mail
            'config=',  # config module
            'change-log-program=',  # send to cl_init
            'template=',  # add to template list
            'max-password-age=',  # max age before notification
            'grace-period=',  # time after notification to chang pw
            'reminder-delay=',  # times after notification to send reminders
            'password-trait=',  # trait to use for password
            'password-quarantine='  # quarantine to use for password
            ])

    except getopt.GetoptError:
        usage(1)

    cfg = {}
    debug_enabled = False
    template_set = False

    for opt, val in opts:
        if opt in ('--help', '-h'):
            usage()
        elif opt in ('--from',):
            cfg['summary_from'] = val
        elif opt in ('--to',):
            cfg['summary_to'] = val
        elif opt in ('--cc',):
            cfg['summary_cc'] = val
        elif opt in ('--bcc'):
            cfg['summary_bcc'] = val
        elif opt in ('--debug',):
            debug_enabled = True
        elif opt in ('--template',):
            if not template_set:
                template_set = True
                cfg['template'] = []
            cfg['template'].append(val)
        elif opt in ('--max-password-age',):
            cfg['max_password_age'] = parse_time(val)
        elif opt in ('--grace-period',):
            cfg['grace_period'] = parse_time(val)
        elif opt in ('--reminder-delay',):
            cfg.get('reminder_delay', []).append(parse_time(val))
        elif opt in ('--change-log-program',):
            cfg['change-log-program'] = val
        elif opt in ('--password-trait',):
            cfg['password-trait'] = co.EntityTrait(val)
            int(cfg['password-trait'])
        elif opt in ('--password-quarantine',):
            cfg['quarantine'] = co.Quarantine(val)
            int(cfg['quarantine'])

    for i in cfg.keys():
        setattr(config, i, cfg[i])

    notifier = PasswordNotifier.get_notifier()(db=db, logger=logger, dryrun=debug_enabled)
    notifier.process_accounts()


def parse_time(time):
    """
    Matches a time string.
    @param time: The string to parse
    @type time: str
    @return: A corresponding date diff
    @rtype:  mx.DateTime.DateTimeDelta
    @raise ValueError: Parsing failed
    @raise TypeError:  time is not of correct type
    Units are years [short: y or year] (365 days),
        months [m|month] (30 days), weeks [w|week] and days [(no unit)|d|day]
    A time string is a sequence of integers followed by units, and units
    must be given from largest to smallest. Whitespace can occur wherever natural.
    examples:
    5 y 2 w => 5 years and 2 weeks
    5 years => 5 years
    3w 1    => 3 weeks and 1 day
    3weeks1day => 3 weeks and 1 day
    1 d 3w  => nothing, weeks must be before days
    1 3 d   => nothing, days given twice
    """
    import re
    year = r"(?P<year>\d+)\s*y(?:ears?)?"     # year  = num y | num year  | num years
    month = r"(?P<month>\d+)\s*m(?:onths?)?"  # month = num m | num month | num months
    week = r"(?P<week>\d+)\s*w(?:eeks?)?"     # week  = num w | num week  | num weeks
    day = r"(?P<day>\d+)\s*(?:d(?:ays?)?)?"   # day   = num   | num d     | num day | num days
    match = re.match(
        pattern="\s*(?:" + r")?\s*(?:".join((year, month, week, day)) + r")\s*",
        string=time,
        flags=re.IGNORECASE)

    # if match failed, or the string had no values:
    if not match or not filter(lambda x: x is not None, match.groups()):
        raise ValueError("%s does not give a parseable time" % time)
    total = dt.DateTimeDelta(0)
    year = match.group('year') or 0
    total += int(year) * 365 * dt.oneDay
    month = match.group('month') or 0
    total += int(month) * 30 * dt.oneDay
    week = match.group('week') or 0
    total += int(week) * dt.oneWeek
    day = match.group('day') or 0
    total += int(day) * dt.oneDay
    return total


def usage(exitcode=0):
    print """Usage: [options]
    Force users to change passwords regularly.

    --from address          : for the summary sent to admin
    --to address            : for the summary sent to admin
    --cc address            : for the summary sent to admin
    --bcc address           : for the summary sent to admin
    --template file         : filename of template. May be given more than
                              once, the corresponding template will be used.
    --max-password-age time : warn when password is older than this # of days
    --grace-period time     : minimum time between warn and splat
    --reminder-delay time   : send a reminder after this number of days
                              after the first message.
    --debug                 : Will not send mail, splat accounts, nor update
                              Cerebrum. Use with --logger-name=console
    --password-trait code   : A password trait code to use for trait
    --password-quarantine q : A the quarantine used by this script

    time values are parsed as a string with numbers and units
    (year [365 days], month [30 days], week, day)
    """
    sys.exit(exitcode)

if __name__ == '__main__':
    main()
