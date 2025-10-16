# -*- coding: utf-8 -*-
#
# Copyright 2024 University of Oslo, Norway
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
"""
Helpers for interacting with Active Directory in scripts.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging
import textwrap

from Cerebrum.utils import argutils
from Cerebrum.utils import secrets
from . import winrm
from . import ADUtils

logger = logging.getLogger(__name__)


# Namespace-attributes for the winrm subparser
OPTION_WINRM_PRESET = "winrm_preset"
OPTION_WINRM_HOST = "winrm_host"
OPTION_WINRM_PORT = "winrm_port"
OPTION_WINRM_SSL = "winrm_ssl"
OPTION_WINRM_CA_CERT = "winrm_ca_cert"
OPTION_WINRM_USER = "winrm_user"

OPTION_WINRM_AD_DOMAIN = "winrm_ad_domain"
OPTION_WINRM_AD_USER = "winrm_ad_user"

# Default ports for the winrm client
#   (this probably belongs in the `.winrm` module)
DEFAULT_WINRM_PORT_HTTP = 5985
DEFAULT_WINRM_PORT_HTTPS = 5986


def _extract_opts(args):
    """ Get options from an ad or winrm subparser namespace result. """
    opts = {}
    for option in (OPTION_WINRM_PRESET,
                   OPTION_WINRM_HOST,
                   OPTION_WINRM_PORT,
                   OPTION_WINRM_SSL,
                   OPTION_WINRM_CA_CERT,
                   OPTION_WINRM_USER,
                   OPTION_WINRM_AD_DOMAIN,
                   OPTION_WINRM_AD_USER):
        value = getattr(args, option, None)
        if value is not None:
            opts[option] = value
    return opts


def get_preset(name, presets):
    """
    Get a given preset from a dict of named presets.

    :param name: A key to look up in the presets dict
    :param presets: A dict of presets (typically `adsync.SYNCS`)

    This is just a convoluted way of getting `adsync.SYNCS[<name>]`, with some
    extra error handling.
    """
    if name not in presets:
        raise ValueError(
            textwrap.dedent(
                """
                Invalid sync preset {name}.

                Valid presets:
                {presets}
                """
            ).format(
                name=name,
                presets="\n".join(
                    " - {}".format(p)
                    for p in sorted(presets)
                ),
            )
        )
    preset = presets[name]
    if not isinstance(preset, dict):
        raise ValueError("Invalid preset {name} - check adconf preests")
    return dict(preset)


def add_winrm_subparser(parser):
    """ Add a winrm client subparser to an existing ArgumentParser. """
    winrm_subparser = parser.add_argument_group(
        "WinRM",
        textwrap.dedent(
            """
            WinRM connection settings.  Settings are loaded from the given
            preset, if given through --type.  Other options will override
            settings from the preset.
            """
        ).lstrip(),
    )
    # Should probably be renamed --preset, but kept as --type for backwads
    # compatibility
    preset_arg = winrm_subparser.add_argument(
        "--type",
        dest=OPTION_WINRM_PRESET,
        help="Get default settings from preset in `adconf.SYNCS[%(metavar)s]`",
        metavar="PRESET",
    )
    host_arg = winrm_subparser.add_argument(
        "--host",
        dest=OPTION_WINRM_HOST,
        help="Host to connect to (required)",
        metavar="HOST",
    )
    winrm_subparser.add_argument(
        "--port",
        type=int,
        dest=OPTION_WINRM_PORT,
        help="Port to connect to (defaults to {}/{})".format(
            DEFAULT_WINRM_PORT_HTTP,
            DEFAULT_WINRM_PORT_HTTPS,
        ),
        metavar="PORT",
    )
    ssl_mutex = winrm_subparser.add_mutually_exclusive_group()
    ssl_mutex.add_argument(
        "--ssl",
        dest=OPTION_WINRM_SSL,
        default=None,
        action="store_true",
        help="Force https (default)",
    )
    ssl_mutex.add_argument(
        "--no-ssl",
        dest=OPTION_WINRM_SSL,
        default=None,
        action="store_false",
        help="Force http",
    )

    winrm_subparser.add_argument(
        "--ca-cert",
        dest=OPTION_WINRM_CA_CERT,
        default=None,
        help="Use a custom CA certificate (PEM-file)",
        metavar="FILENAME",
    )

    # Should we add client key/cert support?

    winrm_subparser.add_argument(
        "--auth-user",
        dest=OPTION_WINRM_USER,
        help="""
          Authenticate with %(metavar)s in WinRM.  Password is read from
          `cereconf.DB_AUTH_DIR`.
        """,
        metavar="USERNAME",
    )

    get_client = _WinrmClientFactory(
        parser,
        preset_arg,
        host_arg,
    )
    return get_client


def add_ad_subparser(parser):
    """ Add an ad client subparser to an existing ArgumentParser. """
    winrm_factory = add_winrm_subparser(parser)

    domain_subparser = parser.add_argument_group(
        "Domain",
        textwrap.dedent(
            """
            Active Directory domain settings.
            """
        ).lstrip(),
    )
    domain_subparser.add_argument(
        "--domain",
        dest=OPTION_WINRM_AD_DOMAIN,
        help="Domain to manage",
        metavar="DOMAIN",
    )
    domain_subparser.add_argument(
        "--domain-user",
        dest=OPTION_WINRM_AD_USER,
        help="""
          User for managing the AD domain.  Password is read from
          `cereconf.DB_AUTH_DIR`.
        """,
        metavar="USERNAME",
    )
    return _AdClientFactory.from_winrm_factory(winrm_factory)


class _WinrmClientFactory(object):
    """ Get a configured winrm client (subclass) from subparser arguments. """

    client_class = winrm.WinRMClient
    client_logger_name = "_winrm_client"

    def __init__(self, subparser, preset_arg, host_arg):
        self._parser = subparser
        self._preset_arg = preset_arg
        self._host_arg = host_arg

    def _get_preset(self, presets, opts):
        with argutils.ParserContext(self._parser, self._preset_arg):
            if OPTION_WINRM_PRESET in opts:
                preset = get_preset(opts[OPTION_WINRM_PRESET], presets)
            else:
                preset = {}
        return preset

    def _get_client_args(self, preset, opts):
        if OPTION_WINRM_SSL in opts:
            use_ssl = opts[OPTION_WINRM_SSL]
        else:
            use_ssl = preset.get("encrypted", True)
        ssl_hint = "https" if use_ssl else "http"

        with argutils.ParserContext(self._parser, self._host_arg):
            if OPTION_WINRM_HOST in opts:
                host = opts[OPTION_WINRM_HOST]
            elif preset.get("server"):
                host = preset['server']
            else:
                raise ValueError("no host given")

        if OPTION_WINRM_PORT in opts:
            port = opts[OPTION_WINRM_PORT]
        elif preset.get("port"):
            port = int(preset['port'])
        else:
            port = (DEFAULT_WINRM_PORT_HTTPS if use_ssl
                    else DEFAULT_WINRM_PORT_HTTP)
            logger.debug("using default port (%d) for WinRM over %s",
                         port, ssl_hint)

        if OPTION_WINRM_CA_CERT in opts:
            ca_cert = opts[OPTION_WINRM_CA_CERT]
        elif use_ssl:
            ca_cert = preset.get("ca")
        else:
            ca_cert = None

        logger.info("using WinRM server at %s://%s:%s", ssl_hint, host, port)

        return {
            'host': host,
            'port': port,
            'encrypted': use_ssl,
            'logger': logger.getChild(self.client_logger_name),
            'ca': ca_cert,
        }

    def _get_auth_user(self, preset, opts):
        auth_user = preset.get("auth_user", None)
        if OPTION_WINRM_USER in opts:
            auth_user = opts[OPTION_WINRM_USER]
        if auth_user:
            logger.info("authenticating as %s", repr(auth_user))
        return auth_user

    def __call__(self, presets, args):
        opts = _extract_opts(args)
        preset = self._get_preset(presets, opts)
        init_args = self._get_client_args(preset, opts)
        auth_user = self._get_auth_user(preset, opts)
        client = self.client_class(**init_args)
        if auth_user:
            logger.info("authenticating as %s", repr(auth_user))
            password = secrets.legacy_read_password(auth_user,
                                                    init_args.get('host'))
            client.add_credentials(username=auth_user, password=password)
        return client


class _AdClientFactory(_WinrmClientFactory):
    """ Get a configured ad client from subparser arguments. """

    client_class = ADUtils.ADclient
    client_logger_name = "_ad_client"

    @classmethod
    def from_winrm_factory(cls, winrm_factory):
        return cls(winrm_factory._parser, winrm_factory._preset_arg,
                   winrm_factory._host_arg)

    def _get_client_args(self, preset, opts):
        init = super(_AdClientFactory, self)._get_client_args(preset, opts)

        if OPTION_WINRM_AD_DOMAIN in opts:
            domain = opts[OPTION_WINRM_AD_DOMAIN]
        else:
            domain = preset.get("domain", None)

        if OPTION_WINRM_AD_USER in opts:
            domain_user = opts[OPTION_WINRM_AD_USER]
        else:
            domain_user = preset.get("domain_admin", None)

        init.update({
            'domain_admin': domain_user,
            'domain': domain,
        })
        return init

    def __call__(self, presets, args, dryrun):
        opts = _extract_opts(args)
        preset = self._get_preset(presets, opts)
        init_args = self._get_client_args(preset, opts)
        init_args.update({
            'auth_user': self._get_auth_user(preset, opts),
            'dryrun': dryrun,
        })
        return self.client_class(**init_args)
