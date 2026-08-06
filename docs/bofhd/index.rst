====
bofh
====

.. toctree::
   :caption: bofh
   :maxdepth: 1
   :glob:

   *

*bofh*, short for *brukerorganisering for hvermannsen*, is a Cerebrum
administration tool.

Bofhd is a XML/RPC server which provides remote administration commands for the
bofh system.  It is indended to be used with interactive *bofh* CLI clients,
like e.g. *pybofh*.


Configuring and extending bofhd
=================================
bofhd requires a basic config file, commonly named ``config.dat``.

This config must contain a list of command implementations to load on startup.
Each line should contain a single command class to load.  See
``Cerebrum.utils.module`` for details on the class import format.

The file supports ``#`` comments, and ignores empty lines.  This is a simple
example with two command modules:
::

    Cerebrum.modules.tasks.bofhd_task_cmds/TraitCommands

    # not sure why some classes use a Bofhd* prefix and others don't.
    # It's useful for demo-ing comments, tough
    Cerebrum.modules.trait.bofhd_trait_cmds/BofhdTaskCommands


Note that a command module typically provides multiple commands!

.. important::
   You typically want to subclass and extend a command class with custom
   authorization mixins!  Using them directly like this means that the *default*
   authorization rules for the command class are used, and can't be overridden.

General bofhd behaviour and business logic is typically contained in a
``cereconf`` config module.


Commands and parameters
-----------------------
The ``Cerebrum.modules.bofhd.bofhd_core`` implements the base command class for
bofhd.

Commands are implemented as simple methods in a command subclass, and are
exposed as remote procedures by mapping it using a ``Command`` object in the
command class ``all_commands`` attribute.


``bofhd_uio_cmds.py``
---------------------
The bofhd module that currently has the most features is
``Cerebrum/modules/no/uio/bofhd_uio_cmds.py``.  Its original purpose
was to support the jbofh client, but other clients has started using
it as well.
