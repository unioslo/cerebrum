=========
Configure
=========

.. toctree::
   :caption: Configstuffs
   :maxdepth: 1
   :glob:

   *

Cerebrum uses multiple configuration files, and configuration systems.

Config modules
==============
The core cerebrum functionality and business logic is configured using *config
modules*, with ``cereconf`` being the most notable.

This also applies to certain optional legacy modules.

Other configuration modules only serves as a *default* config for scripts that
use python config files.  These scripts will typically accept a config file
using command-line options, and defaults to *importing* the specified module
when no options are given.  To prevent a default from existing, simply do not
make it importable.

See :doc:`config-modules` for a list of these modules and a short
description.


Config files
=============
``Cerebrum.config`` implements a framework for implementing Cerebrum
sub-component configuration.

Most individual features uses this config framework, and some of these supports
*auto-loading* a config from the Cerebrum root config directory,
``CEREBRUM_CONFIG_ROOT``.  This is ``<sys-prefix>/etc/cerebrum/config`` by
default, but it can be overridden by an environment variable.

See :doc:`config-files` for a list of these files and a short description.


Other configs
=============

bofhd
------
The :doc:`/bofhd/index` server uses its own config for loading command
implementations.  This file is given as a cli-option when starting the server.
