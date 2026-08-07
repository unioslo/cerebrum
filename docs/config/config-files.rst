====================
Configuration files
====================

This document lists configuration files for the :doc:`structured-configs`.

Note that some configs can be auto-loaded from the ``CEREBRUM_CONFIG_ROOT``
directory, and that parts of those config files can be split into separate
config files.

Also, if a config file exists in two separate formats (e.g. a ``foo.json`` and a
``foo.yaml``), then both files will be read.  The order in which the files are
read is not well defined.


Common config files
====================
Config files that affects *common* cerebrum features.  These config files are
always auto-loaded.

.. todo::
   We should probably consider moving all these settings back into ``cereconf``,
   as these settings are required.  We could still use the config framework to
   parse and validate the settings.


gpg_data
---------
Configure recipient keys supported by ``Cerebrum.modules.gpg``.

This file is typically required if any of the ``Cerebrum.modules.gpg`` mixins
are in use.  See :doc:`/gpg/index` for more info.

Note that any key provided here must *also* be imported and present in the
public keyring of the GPG homedir configured in ``cereconf.GNUPG_HOME``.


logutils
---------
Configures the logging environment.  This file is not strictly required, but
very strongly recommended.

See :doc:`/logging/logutils` for more details on this config.


password_generator
-------------------
Configures the password generator rules.  This file is optional, and only used
to change the password generator rules.


statsd
-------
Configures the default ``Cerebrum.modules.statsd`` client.  Witout a config,
metrics will be disabled.

This file is used for parts of Cerebrum with metrics support.  This includes
bofhd and the API.


templates
----------
Templates config for the bofhd print templating system
(``Cerebrum.modules.templates.config``).

Required when any bofhd password letter print commands are included in the bofhd
config.

.. todo::
   ``Cerebrum.modules.templates`` should be refactored and simplified a bit.


Sub-components
===============
Config files that only are in use by certain jobs or scripts.

These config files can be auto-loaded from ``CEREBRUM_CONFIG_ROOT``.


dbfg_update
------------
Configure databases to use in ``contrib/no/uio/dbfg_update.py``.

.. note::
   This config can *only* be auto-loaded - it cannot be overridden by
   cli-options.


enforce_forward_policy
-----------------------
Configure the policy enforced by ``contrib/no/uio/remove_email_forwards.py``


event_daemon
-------------
Config for the event publisher, ``Cerebrum.modules.event_publisher``.  Only
required when running the event publisher daemon.

event_formatter
~~~~~~~~~~~~~~~
This can be configured in the ``event_daemon`` as well, or autoloaded from this
name.

This configures the ``Cerebrum.modules.event_publisher.scim`` formatter, and
configures ``iss`` and other SCIM message fields.

event_publisher
~~~~~~~~~~~~~~~
This can be configured in the ``event_daemon`` as well, or autoloaded from this
name.

This configures the ``Cerebrum.modules.amqp`` client used by the event
publisher.


exchange
---------
Configures the Exchange integration, and is only required when running the
exchange daemon.  See ``Cerebrum.modules.exchange`` for details.


orgreg-client
-------------
Orgreg client config (``Cerebrum.modules.orgreg.client``).

Autoloaded by ``contrib/orgreg/orgreg-fetch-legacy-xml.py``, but can be
overridden by a cli-option.  This import can also load data from a cache - in
which case no client config is required.


password_notifier
------------------
Configures the ``Cerebrum.modules.password_notifier`` rules.

This file is optional, and (only) loaded by the password notifier script, and
only when no other config is given using cli-options.


Other configs
--------------
Some config files can't be auto-loaded from ``CEREBRUM_CONFIG_ROOT``, but can
still be defined and used by individual scripts or modules from command line
arguments.

consume-tasks
~~~~~~~~~~~~~
Configure an AMQP server and exchanges to consume with 
``consumers/consume-tasks.py``.

greg-client
~~~~~~~~~~~
Greg client config (``Cerebrum.modules.greg.client``).

Only required when using the ``contrib/greg/`` scripts, where the config must be
given as a cli-option.

hr-import
~~~~~~~~~
HR-import configs (``Cerebrum.modules.hr-import``), and typically a client, e.g.
``Cerebrum.modules.no.dfo.client``)

Only required when using the ``contrib/hr-import/`` scripts, where the config must be
given as a cli-option.
