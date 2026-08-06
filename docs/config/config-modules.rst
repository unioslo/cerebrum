=====================
Configuration modules
=====================

.. important::
   Some configuration modules are required to be present and importable for the
   specific Cerebrum component to work.

   The ``cereconf`` module is *always* required.


cereconf
========
The Cerebrum core config.  This module defines common business logic, and base
classes used throughout Cerebrum.

Most settings have a default value in ``Cerebrum.default_config``, and every
setting is documented in this module using *comments*.  Every deployment should
have a ``cereconf`` module, and that module *should* start off by doing:
::

    from Cerebrum.default_config import *  # noqa: F401, F403

See :doc:`cereconf` for more info on this config module.


adconf
=======
This module is optional, but must be present when using the Active Directory
integration from ``Cerebrum.modules.ad2``.

The config defines a set of *sync profiles*, and each profile specifies:

- Which sync implementation to use
- Which objects to sync from Cerebrum
- Where to sync to (host + auth + domain + ou)
- Which attributes to sync
- How to deal with deleted objects

This config is not well documented - please refer to real-world examples, or
code in ``Cerebrum.modules.ad2``.


file_clean_conf
================
Configures archiving and cleanup maintenance tasks.

.. note::
   This module doesn't need to be importable - it can be overridden using cli-options.

See :doc:`/maintenance/index` for more details.


guestconfig
============
This module is optional, but must be present when using
``Cerebrum.modules.guest``.

The settings from this config sets the rules for guest accounts managed through
the ``Cerebrum.modules.guest`` functionality.

Most settings have a default value in ``Cerebrum.modules.guest.default_config``,
and every setting is documented here using *comments*.  When using the guest
module, your deployment should have a ``guestconfig``, ant that module should
start off by doing:
::

    from Cerebrum.modules.guest.default_config import *  # noqa: F401, F403


opset_config
=============
Defines operation sets (opsets) of permissions or operations that should be
available in :doc:`/bofhd/index`.

.. note::
   This module doesn't need to be importable - it can be overridden using
   cli-options.

The config is only used to manually *update* the actual opsets in the database.

.. todo::
   Add some more info on permission updates.


restconfig
===========
This module is optional, and only applies to the ``Cerebrum.rest`` API.

This is a basic ``flask`` config module, and supports all common *flask* and
*flask-restplus* settings.

The ``Cerebrum.rest.default_config`` module defines some default settings.
Unlike `cereconf`_, there is no need to manually import these in your config -
the default settings are automatically applied, and overridden by any settings
in ``restconfig``.


scheduled_jobs
===============
Defines all jobs to be scheduled using ``Cerebrum.modules.job_runner``.

.. note::
   This module doesn't need to be importable - it can be overridden using
   cli-options.

.. todo::
   Document job-runner


Other config files
==================

.. todo::
   Document these configs as well!

- ``*_ldap_conf``
- ``dbcl_conf`` + entry in maintenance/
- ``eventconf``
- ``file_clean_conf``
