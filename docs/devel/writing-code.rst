==========================
Writing code for Cerebrum
==========================

Code style
===========
Please read through the :doc:`code-style` documents before writing any Cerebrum
code.


Code placement
===============

Core features
    This includes all common code, always available to all environments.

    Modules in ``Cerebrum/``, or scripts/cronjons in ``contrib/``

Optonal features
    Code that only applies to some environments, typically optional features.
    May need optional database-schemas.

    Modules in ``Cerebrum/modules/``, or scripts/cronjons in ``contrib/<feature>``

Environment-specific features
    Code that only applies to a single environment.

    Modules in ``Cerebrum/modules/no/<env>``, or scripts/cronjons in ``contrib/no/<env>``


Writing Modules
================
Modules should always start with the following preamble and code:

encoding declaration comment
    Example: ``# -*- coding: utf-8 -*-``

License blurb
    A GPL3 license header, with up-to-date years:
    ::

        # Copyright 2002-2010 University of Oslo, Norway
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

A docstring
    A short description on what the module is/does/intends.

    Document external factors, e.g. cereconf config values that directly impact
    the module behaviour.

    Document any odd conventions, terminology, etc...

Future-imports
    All new code should include:
    ::

        from __future__ import (
            absolute_import,
            division,
            print_function,
            unicode_literals,
        )


Writing scripts
================
Scripts in ``contrib/`` are mostly scheduled cron-style jobs to run
periodically.

All runnable scripts in ``contrib/`` should start with the following *hashbang*:
::

    #!/usr/bin/env python

This should be immediately followed by the same preamble as `modules`_.

Very few constraints apply to the rest of the script:

- always use ``argparse`` to parse input arguments
- always add log setup using ``Cerebrum.logutils`` and
  ``Cerebrum.logutils.options``
- always run in *dryrun* by default if the script affects the database or any
  other state (e.g. remote commands).
- always use a ``if __name__ == "__main__"``-block to make the script itself
  importable without side effects.


.. See :doc:`example-cronjob` for an example.
