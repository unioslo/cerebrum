=============================
Writing scripts for Cerebrum
=============================

.. contents::

.. section-numbering::


Standards for scripts in Cerebrum, i.e. the typical *cronjob*.  Scripts in
Cerberum should generally be *small and simple*:

- They provide an interface from the command line + environment and Cerebrum
- Most of the functinality should be placed in *modules*, where it can be tested
  and reused


Header
=======

Hashbang
--------
All scripts should start with the following *hashbang*:
::

    #!/usr/bin/env python


Encoding
---------
Use *utf-8* in all scripts and modules, and add an encoding hint after the
*hashbang*:
::

    # -*- coding: utf-8 -*-


License
-------
Include the following copyright + GPLv3 license notice, and remember to update
the copyright year when adding or updating a file:
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
Document the script in a module docstring.  This should explain what the script
does, and how it should be used:
::

    """
    This script does so and so.

    More elaborate description follows here. ...
    """


Command line parameters
========================
Use the ``argparse`` module for parsing parameters.  Cerebrum includes some
argparse helpers in ``Cerebrum.utils.argparse`` and
``Cerebrum.logutils.options``.


Commit / dryrun
---------------
Many scripts mutates the database, and can cause changes that aren't easily
rolled back.  These scripts should always include ``--commit``/``--dryrun``
options, and:

- use *dryrun* as the default
- log/print the chosen mode of operation on startup
- log/print on commit or rollback

Use ``Cerebrum.utils.argutils.add_commit_args`` to add these arguments.


Logging
=======
Add a module level logger to the script, and configure logging early.

Configure the logging as early as possible, as our ``Cerebrum.logutils`` needs
to process ``sys.argv``, *and* set up some globals (e.g.  change how exceptions
and warnings are handled).

Scripts without special needs should use ``Cerebrum.logutils`` and the standard
logger presets:
::

    logger = logging.getLogger(__name__)

    def main():
        Cerebrum.logutils.autoconf('cronjob', ...)

See the `logging docs <../../logging>`_ for more info.


Writing files
==============
Use one of the ``Cerebrum.utils.atomicfile`` classes to write important files
(like batch exports) from cronjobs.

These file-like objects will only replace a file on close, and includes sanity
checks that disallows replacement if the resulting file is empty or has too many
changes.
