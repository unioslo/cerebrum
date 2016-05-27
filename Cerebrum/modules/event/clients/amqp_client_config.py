#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
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
""" This module defines all necessary config for the base AMQP client. """

from Cerebrum.config.configuration import (ConfigDescriptor,
                                           Configuration)

from Cerebrum.config.settings import (Boolean,
                                      Integer,
                                      String)


class BaseAMQPClientConfig(Configuration):
    u"""Configuration for the basic AMQP client."""
    username = ConfigDescriptor(String,
                                default=u"cerebrum",
                                doc=u"Username used for authetication")

    hostname = ConfigDescriptor(String,
                                default=u"localhost",
                                doc=u"Hostname of broker")

    port = ConfigDescriptor(Integer,
                            default=u"5762",
                            doc=u"Portnumber of broker")

    virtual_host = ConfigDescriptor(String,
                                    default=u"no/uio/cerebrum",
                                    doc=u"Vhost that queues and exchanges "
                                        "reside on")

    tls_on = ConfigDescriptor(Boolean,
                              default=True,
                              doc=u"Use TLS for communication")
