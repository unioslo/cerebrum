=============
Writing code
=============

Code style
===========
Please read through the :doc:`code-style` before writing code
for Cerebrum.


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

Unit tests
    Unit tests should be placed in ``testsuite/tests/``.  See
    :doc:`unit-tests` for more info on how to organize test modules.


Common fixtures
================
All Cerebrum modules and scripts should include the following parts.

Hashbang
--------
All *scripts* should start with the following hashbang:
::

    #!/usr/bin/env python

Note that this only applies to scripts — importable modules should *not* have
this comment!


Encoding
---------
Use *utf-8* in all scripts and modules, and add an encoding hint!  For scripts,
this should follow immediately after the `hashbang`_.  For modules this should
be the first line.
::

    # encoding: utf-8


License
-------
Include the following copyright + GPLv3 license notice immediately after the
`encoding`_ declaration, and remember to update the copyright year
when adding or updating a file:
::

    # This file is part of Cerebrum.
    # Copyright (C) 2010-2023 University of Oslo, Norway
    #
    # This program is free software: you can redistribute it and/or modify
    # it under the terms of the GNU General Public License as published by
    # the Free Software Foundation, either version 3 of the License, or
    # (at your option) any later version.
    #
    # This program is distributed in the hope that it will be useful,
    # but WITHOUT ANY WARRANTY; without even the implied warranty of
    # MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    # GNU General Public License for more details.
    #
    # You should have received a copy of the GNU General Public License
    # along with this program.  If not, see <https://www.gnu.org/licenses/>.


Docstring
----------
Document the script or module with a docstring:
::

    """
    This script does so and so.

    More elaborate description follows here. ...
    """

See :doc:`doc-style` for more info on what to include here.


Compatibility imports
----------------------
Until the codebase is completely Python 3.6+ compatible, the following
``__future__`` imports should be present in all modules and scripts:
::

    from __future__ import (
        absolute_import,
        division,
        print_function,
        unicode_literals,
    )


Common patterns
================
Some common patterns for scripts and modules.


Command line parameters
------------------------
Prefer the ``argparse`` module for parsing, noramlizing and validating command
line parameters.  Cerebrum includes some argparse helpers in
``Cerebrum.utils.argparse`` and ``Cerebrum.logutils.options``.


Logging
--------
Use a module level logger in any script or module that logs.
::

    logger = logging.getLogger(__name__)

For scripts, configure logging as early as possible.

Scripts without special needs should use ``Cerebrum.logutils`` and the standard
logger presets:
::

    def main():
        Cerebrum.logutils.autoconf('cronjob', ...)

See :doc:`/logging/how-to` for more info.


Commit / dryrun
----------------
Many scripts mutates the database, and can cause changes that aren't easily
rolled back.  These scripts should always include ``--commit``/``--dryrun``
options, and:

- use *dryrun* as the default
- log/print the chosen mode of operation on startup
- log/print on commit or rollback

Use ``Cerebrum.utils.argutils.add_commit_args`` to add these arguments.

It's also good practice to follow these guidelines for scripts that cause other
side effects.  E.g. sending mail, deleting files, etc...


Writing files
--------------
Use one of the ``Cerebrum.utils.atomicfile`` classes to write important files
(like batch exports) from cronjobs.

These file-like objects will only replace a file on close, and includes sanity
checks that disallows replacement if the resulting file is empty or has too many
changes.


main-fence
-----------
Scripts (and runnable modules) should always place code in a ``main`` function,
and include a code-fence to prevent side-effects on import:
::

    if __name__ == "__main__":
        main()


About modules
==============
All modules in Cerebrum should be placed in the ``Cerebrum`` namespace.

Some other things to consider when writing a module:

Complexity
    All modules, classes, methods, and functions should solve *one* specific problem.

Protected names
    While Python doesn't have public/protected/private keywords, it's common to
    use ``_``/``__`` prefixes to indicate intended use for named objects or
    constants.

Naming
    When naming *public* module-level names, take into consideration *where*
    that name might be used elsewhere in the code base.  The name should make
    sense both within the module that defines it, *and* in the scope where it
    will most likely be used.


About scripts
==============
Scripts in ``contrib/`` are mostly scheduled cron-style jobs to run
periodically.

Scripts in Cerberum should generally be *small and simple*, and provide an
interface from the command line + environment to Cerebrum.

Most of the functinality triggered from a script should be implemented in
*modules*, where it can be tested and reused.

.. See :doc:`example-cronjob` for an example.
