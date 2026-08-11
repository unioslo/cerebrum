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


dbcl_conf
==========
This module is optional, but must be present when using the db cleaner
(``contrib/db_clean.py``).

.. todo::
   Document db-cleaner in maintenance/

This config have default settings in ``Cerebrum.modules.default_dbcl_conf``, and
the comments in this module describes the various settings.


eventconf
==========
This config module was intended to configure the ``Cerebrum.modules.EventLog``
and ``Cerebrum.modules.event`` subsystem.  However, this system is only in use
by the *Exchange* integration (exchange_deamon).

The config is similar to ``adconf``, where the config contents is a mapping of
*profiles*.  Each profile should match a *target system* for the EventLog.

The only *required* setting, is the ``fail_limit`` — i.e. how many times event
processing should run for an event before considering it to be *failed*.  All
other settings are tacked on for use by the individual target system
integration.  For Exchange, the settings are used by the LDAP verification
scripts.


file_clean_conf
================
Configures archiving and cleanup maintenance tasks for files and directories.

.. note::
   This module doesn't need to be importable - it can be overridden using cli-options.

See :doc:`/maintenance/file-cleaner` for more details.


guestconfig
============
This module is optional, but must be present when using
``Cerebrum.modules.guest``.

The settings from this config sets the rules for guest accounts managed through
the ``Cerebrum.modules.guest`` functionality.

Most settings have a default value in ``Cerebrum.modules.guest.default_config``,
and every setting is documented here using *comments*.  When using the guest
module, your deployment should have a ``guestconfig``, and that module should
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

The config is only used to manually *update* the actual opsets in the database,
using ``contrib/permission_updates.py``

Settings
---------

``operation_sets``
    A mapping of opset name to opset.  The actual opset is a mapping of
    operation name to operation settings.  The only current operation setting is
    ``attrs``, an optional attribute limit (op-attrs) for the operation.

    Example:
    ::

        operation_sets = {
            'Group-Owner-Foo': {
                'search_group': {},
                'create_group': {
                    'attrs': ["pre:foo-"],
                },
            },
        }

    This config would contain a single opset, which would grant access to search
    for all groups, and to create groups with a ``foo-`` name prefix.

    The setting is only used with the ``--import`` or ``--clean`` flags.

``convert_mapping``
    A mapping of old-name to new-name for operation sets.  This mapping can be
    used to rename opsets.

    The setting is only used with the ``--convert`` flag.


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
Defines jobs for *job-runner*, the Cerebrum scheduler.

.. note::
   This module doesn't need to be importable - it can be overridden using
   cli-options.

See :doc:`/job-runner/config` for details on how to configure job-runner.


\*_ldap_conf
=============
In addition to the ordinary Feide export, Cerebrum can generate additional Feide
LDAP catalogues for certain *selections* of user accounts.  These will usually
load their config from a ``foo_ldap_conf`` config module.

These exports work very similar to the usual Feide export, but they read their
Feide/LDAP configuration from the provided module rather than ``cereconf``.

This includes the typical Feide ldap settings:

- ``CLASS_ORGLDIF``
- ``DEFAULT_INSTITUSJONSNR``
- ``INSTITUTION_DOMAIN_NAME``
- ``LDAP``
- ``LDAP_ORG``
- ``LDAP_OU``
- ``LDAP_PERSON``


``sysadm_ldap_conf``
    Used by ``contrib/no/uio/generate_sysadm_ldif.py``, and exports sysadm
    accounts to a Feide-like LDAP tree.

    The script is hard-coded to import the ``sysadm_ldap_conf`` config module.

``<randsone>_ldap_conf``
    Used by ``contrib/no/uio/generate_randsone_ldif.py``, and exports uses from a
    given ou sub-tree to a Feide-like LDAP tree.

    The selection is done by:

    - Setting a root ou id in ``LDAP_ORG['ou_id']``
    - Selecting affiliation types in
      ``LDAP_PERSON['eduPersonAffiliation_selector']``.

    The script is hard-coded to import the ``<randsone>_ldap_conf`` config
    module, where ``<randsone>`` is provided using the mandatory ``-i`` option.
