<<<<<<< HEAD
#!/usr/bin/env python
# -*- coding: utf-8 -*-
=======
#! /usr/bin/env python
# encoding: utf-8
>>>>>>> python-27-pseudo-master
#
# Copyright 2015 University of Oslo, Norway
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

"""Errors thrown by wrapped clients used by EventPublisher."""


class ConfigurationFormatError(Exception):
    """Error related to config format."""
    pass


class MessageFormatError(Exception):
    """Error related to message-format."""
    pass


class MessagePublishingError(Exception):
    """Error related to message publishing."""
    pass


class ConnectionError(Exception):
    """Error related to client → broker connection."""
    pass


class ProtocolError(Exception):
    """Error related to protocol used."""
    pass
