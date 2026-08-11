=========
Configure
=========

Cerebrum uses multiple configuration files, and configuration systems.

Config modules
==============
The core cerebrum functionality and business logic is configured using *config
modules*, with :doc:`cereconf` being the most notable.

Some config modules are typically required to exist and be importable for
certain *features* of Cerebrum to work properly.

Other configuration modules only serves as the *default* config file for scripts
that use python config files.  These scripts will typically accept a config file
using command-line options, and defaults to *importing* the specified module
when no config option is given.  To prevent a default from existing, simply do
not make it importable.

See :doc:`config-modules` for a list of these modules and a short
description.


Config files
=============
``Cerebrum.config`` implements a framework for implementing Cerebrum
sub-component configuration. See :doc:`structured-configs` for more info on how
to use this framework to load configuration in scripts.

Most individual features uses this config framework, and some of these configs
supports *auto-loading* a config file from the Cerebrum root config directory,
``CEREBRUM_CONFIG_ROOT``.  This is ``<sys-prefix>/etc/cerebrum/config`` by
default, but it can be overridden by an environment variable.

See :doc:`config-files` for a list of these files and a short description.


More info
==========

.. toctree::
   :maxdepth: 1
   :glob:


   config-modules
   structured-configs
   config-files
   *


bofhd
------
The :doc:`/bofhd/index` server uses its own config for loading command
implementations.  This file is given as a cli-option when starting the server.
