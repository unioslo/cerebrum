#!/usr/bin/env python
# -*- encoding: utf-8 -*-
""" Config example. """

import sys
from os.path import join as pj

from Cerebrum.config.configuration import Configuration
from Cerebrum.config.configuration import ConfigDescriptor
from Cerebrum.config.configuration import Namespace

from Cerebrum.config.settings import Setting
from Cerebrum.config.settings import String
from Cerebrum.config.settings import Integer
from Cerebrum.config.settings import Numeric
from Cerebrum.config.settings import Boolean
from Cerebrum.config.settings import Iterable


class BofhdConfig(Configuration):

    motd_file = ConfigDescriptor(
        Setting,
        # TODO: Implement a default None-value that passes validation? This is
        #       a setting that often gets disabled by setting None.
        default=None,
        doc="Username for the SMS gateway.")

    superuser_group = ConfigDescriptor(
        String,
        # TODO: Implement callbacks to other config groups, so we can say that
        #       the default value is whatever INITIAL_GROUPNAME is?
        default='cerebrum',
        doc="A group that grants superuser rights in bofhd.")

    studadm_group = ConfigDescriptor(
        String,
        default='cerebrum',
        doc="A group that grants studadm rights group.")

    fnr_access_group = ConfigDescriptor(
        Setting,
        default=None,  # TODO: String-value with default-disable?
        doc="A group that grants studadm rights group.")

    superuser_set_passwords = ConfigDescriptor(
        Boolean,
        default=False,
        doc="Allow superuser to specify passwords for users.")

    # TODO: Should this be configurable?
    #       Or at the very least be a general Cerebrum config thing?
    new_user_spreads = ConfigDescriptor(
        Iterable,
        template=String(),
        default=[],
        doc="A list of spreads for users created with user_create.")

    new_group_spreads = ConfigDescriptor(
        Iterable,
        template=String(),
        default=[],
        doc="A list of spreads for groups created with group_create.")

    max_matches = ConfigDescriptor(
        Integer,
        default=250,
        minval=0,
        doc=("Max number of results from bofh (person_find,"
             " group_list_extended)."))

    check_disk_spread = ConfigDescriptor(
        Setting,
        default=None,
        doc="TODO: Don't know what this is...")

    timeout = ConfigDescriptor(
        Integer,
        default=10,
        minval=0,
        doc="Client socket timeout (in seconds?).")

    request_lockdir = ConfigDescriptor(
        String,
        default=pj(sys.prefix, 'var', 'lock', 'bofhreq', 'lock-%d'),
        doc=("A directory for 'bofhd-requests' lock files."
             " Must include template filename (with '%d' format specifier)."))

    allow_quarantines = ConfigDescriptor(
        Iterable,
        template=String(),
        default=[],
        doc=("A list of quarantines (string constants) that should allowed"
             " to log into bofhd."))

    quarantine_disable_days = ConfigDescriptor(
        Setting,
        default=None,
        doc=("Max number of days that a quarantine can be disabled"
             " with `quarantine_disable`."))

    auth_systems = ConfigDescriptor(
        Iterable,
        template=String(),
        default=['system_manual', ],
        doc=("Authoritative source system for bofhd."
             " TODO: What does this really do?"))


class SMSConfig(Configuration):

    user = ConfigDescriptor(
        String,
        default='cerebrum',
        doc="Username for the SMS gateway.")

    system = ConfigDescriptor(
        String,
        default='USIT',
        doc="Name of this system in the SMS gateway.")

    url = ConfigDescriptor(
        String,
        default='https://localhost/sms',
        doc="Url to the SMS gateway.")


class DatabaseConfig(Configuration):

    host = ConfigDescriptor(
        String,
        default="localhost",
        doc="Database hostname")

    port = ConfigDescriptor(
        Integer,
        minval=0,
        maxval=65535,
        default=5432,
        doc="Database port")

    owner = ConfigDescriptor(
        String,
        default='cerebrum',
        doc="Username of the table owner.")

    user = ConfigDescriptor(
        String,
        default='cerebrum',
        doc="Username of the database user.")

    db = ConfigDescriptor(
        String,
        default='cerebrum',
        doc="Name of the Cerebrum database.")


class JobRunnerConfig(Configuration):

    socket = ConfigDescriptor(
        String,
        default=pj(sys.prefix, 'var', 'lock', 'job_runner'),
        doc="Path to the JobRunner daemon control socket.")

    logdir = ConfigDescriptor(
        String,
        default=pj(sys.prefix, 'var', 'log', 'job_runner'),
        doc="Path to the JobRunner logs.")

    max_jobs = ConfigDescriptor(
        Integer,
        default=3,
        doc="Max simultaneous jobs in JobRunner")

    pause_warn = ConfigDescriptor(
        Numeric,
        default=3600 * 12,
        doc="Warn if JobRunner has been paused for more than N seconds.")


def mixin_config(attr, cls):
    return type('_ConfigMixin',
                (Configuration, ),
                {attr: ConfigDescriptor(Namespace, config=cls,)})


class Config(
        mixin_config('db', DatabaseConfig),
        mixin_config('sms', SMSConfig),
        mixin_config('bofhd', BofhdConfig),
        mixin_config('job_runner', JobRunnerConfig),
        Configuration):
    pass
