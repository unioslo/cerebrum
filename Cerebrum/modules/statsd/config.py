# encoding: utf-8
#
# Copyright 2017 University of Oslo, Norway
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
""" Cerebrum statsd client config. """
from __future__ import absolute_import, print_function

from Cerebrum.config.configuration import ConfigDescriptor, Configuration
from Cerebrum.config.loader import read, read_config
from Cerebrum.config.settings import Boolean, Integer, String, Iterable
from Cerebrum.utils.module import SOURCE_RE


CONFIG_BASENAME = 'statsd_metrics'


class StatsConfig(Configuration):
    """ Global statsd configuration. """

    enable = ConfigDescriptor(
        Boolean,
        default=False,
        doc="enable sending statsd metrics")

    prefix = ConfigDescriptor(
        String,
        regex=r'^(?:[_a-zA-Z0-9](?:[^:|]*[_a-zA-Z0-9])|)$',
        default="cerebrum.undefined",
        doc="prefix for statsd metrics")

    host = ConfigDescriptor(
        String,
        default="localhost",
        doc="statsd hostname/ip")

    port = ConfigDescriptor(
        Integer,
        default=8125,
        minval=0,
        maxval=65535,
        doc="statsd port")

    ipv6 = ConfigDescriptor(
        Boolean,
        default=False,
        doc="allow IPv6 when communicating with statsd")

    mixins = ConfigDescriptor(
        Iterable,
        template=String(regex=SOURCE_RE.pattern),
        default=[],
        doc="mixins for the statsd client class.")


def load_config(filename=None):
    config_cls = StatsConfig()
    if filename:
        config_cls.load_dict(read_config(filename))
    else:
        read(config_cls, CONFIG_BASENAME)
    config_cls.validate()
    return config_cls


# python -m Cerebrum.modules.statsd.config

if __name__ == '__main__':
    import sys
    from pprint import pformat

    def indent(p, prefix="  "):
        return prefix + ("\n" + prefix).join(p.split("\n"))

    # Print documentation
    # TODO: Fix re.VERBOSE regex output in documentation
    print("Documentation:\n")
    print(indent(StatsConfig.documentation()))
    print()

    # Try to print current config, or config from argument
    filename = sys.argv[1] if len(sys.argv) > 1 else None
    print("Config from {0}:\n".format(filename or '<confdir>'))
    config = load_config(filename=filename)
    print(indent(pformat(config.dump_dict())))
    print()
