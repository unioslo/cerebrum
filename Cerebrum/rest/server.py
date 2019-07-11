#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016-2019 University of Oslo, Norway
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
from Cerebrum.rest.api import create_app

app = create_app('restconfig')


def main(inargs=None):
    import argparse
    import Cerebrum.logutils
    import Cerebrum.logutils.options

    parser = argparse.ArgumentParser(
        description="Start flask dev server",
    )

    bind_opts = parser.add_argument_group('bind options')
    bind_opts.add_argument(
        '--host',
        default=app.config['HOST'],
        help='Listen on interface %(metavar)s (%(default)s)',
        metavar='<host>',
    )
    bind_opts.add_argument(
        '--port',
        type=int,
        default=app.config['PORT'],
        help='Listen on port %(metavar)s (%(default)s)',
        metavar='<port>',
    )

    debug_opts = parser.add_argument_group('debug options')
    debug_mutex = debug_opts.add_mutually_exclusive_group()
    debug_default = app.config['DEBUG']
    debug_mutex.add_argument(
        '--debug',
        dest='debug',
        action='store_true',
        help='Enable debug mode' + (' (default)' if debug_default else ''),
    )
    debug_mutex.add_argument(
        '--no-debug',
        dest='debug',
        action='store_false',
        help='Disable debug mode' + ('' if debug_default else ' (default)'),
    )
    debug_mutex.set_defaults(debug=debug_default)

    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('console', args)

    # Fix flask logging
    app.logger.propagate = True
    for handler in app.logger.handlers[:]:
        app.logger.removeHandler(handler)

    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug,
    )


if __name__ == '__main__':
    main()
