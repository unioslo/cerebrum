# -*- coding: utf-8 -*-
# Copyright 2013 University of Oslo, Norway
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
"""Default Cerebrum settings for the integration against Exchange

Overrides should go in a local, instance specific module named:

    eventconf.py

"""


CONFIG = dict()
""" The configuration structure.

Each configuration is a dictionary within the CONFIG dictionary. The key is the
configuration type. Config selection is done with the ``--type`` option to the
event daemon.


Event daemon configuration
==========================
The event daemon understands the following settings.

event_handler_class
    A class to process dispatched events. The event handler may require
    additional configuration.

concurrent_workers
    Number of threads to use. Each thread will run one event_handler_class to
    process events.

event_queue_class
    The class to used to queue events. This setting is optional, and defaults
    to ``Cerebrum.modules.event.BaseQueue``.

event_channels
    TODO


Exchange event handler
=======================
Exchange configuration dictionary consists of the following settings.

Mandatory settings
-------------------
The configuration structure *must* contain the following keys and values.

domain
    The AD resource domain

server
    The springboard server to use

management_server
    The server where the Exchange commands should be executed

port
    Port number for WinRM

auth_user
    Domain and Username for to use with WinRM.

domain_admin
    Domain\\Username for an account that has read access to the main AD

ex_domain_admin
    Domain\\Username for an admin user in the AD resource domain. This user
    must have access to create mailboxes, etc...

Passwords for all users should be available in the ``cereconf.AUTH_DIR``, so
that it can be fetched with ``read_password()``.


Optional configuration
----------------------
The following keys are recognized and in the configuration structure.

ca
    A CA certificate to use with WinRM. If present, a WinRM certificate is
    *required* and will be validated.

    If no CA is given, a Warning will be dispatched for each connection that is
    made.

"""
