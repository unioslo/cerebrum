===================
Feide auth modules
===================

Individual service levels
==========================
Service levels are implemented by the ``Cerebrum.modules.feide`` modules (and
``mod_feide_service``).

Note that this module only implements the ``norEduPersonServiceAuthnLevel``
attribute for individual users and/or services.  You will also need something to
set the ``norEduPersonAuthnMethod`` to support *strong authentication*/MFA.


To enable service level support:

1. Add schema, classes, constants
2. Create/subclass bofhd and orgldif classes.


Add schema
-----------
Must be done before anything else:
::

    python makedb.py design/mod_feide_service.sql


Add class mixins
-----------------
In ``cereconf``, add:

``CLASS_CONSTANTS``
    Add ``"Cerebrum.modules.feide.Constants/Constants"`` for basic feide service
    constants.


``CLASS_CLCONSTANTS``
    Add ``"Cerebrum.modules.feide.Constants/CLConstants"`` for basic feide
    service change types.

``CLASS_PERSON``
    Add ``"Cerebrum.modules.feide.service/FeideServiceAuthnLevelMixin"`` for
    feide service bindings on persons.

``CLASS_GROUP``
    Add ``"Cerebrum.modules.feide.service/FeideServiceAuthnLevelMixin"`` for
    feide service bindings on groups.



Insert constants
-----------------
Run makedb to insert the constants from the new mixins:
::

    python makedb.py --only-insert-codes


Subclass and add modules
------------------------
Bofhd
    Base implementation in ``Cerebrum.modules.feide.bofhd_feide_cmds/BofhdExtension``.

    Create a subclass of the commands to mix in the localized authorization
    class, and optionally to override the authorization implementations.

    For basic functionality, simply create a subclass (e.g.
    ``Cerebrum.modules.no.example.bofhd_cmds:FeideServiceCommands``), and add
    the subclass to the bofhd ``config.dat`` config.

OrgLDIF
    Base implementation in ``Cerebrum.modules.feide.ldif_mixins.NorEduAuthnLevelMixin``.

    Add the OrgLDIF mixin to the local ``OrgLDIF`` implementation, or to the
    ``cereconf.CLASS_ORGLDIF`` base classes.


Basic usage
------------

1. Define a service: ``feide service_add <service-id> <service-name>``
2. Set authn level for a person: ``feide authn_level_add <service-name> person:<username> <authn-level>``


``<service-id>``
    *service-id* is a reference to the actual service.  The ID for a given
    service can be found in the Feide portal.  It must be correct, otherwise we
    may target *another* service (or a non-existing service).

    A service with the special value ``all`` can be defined to refer to all
    services.

``<service-name>``
    A unique identifier to represent the service in a more human-friendly way
    in Cerebrum (e.g. ``"canvas-prod"``).   Like a username for the service.
    This has no effect outside of Cerebrum.

``<authn-level>``
    The required authentication level - A literal ``3`` is username/password,
    and ``4`` is MFA (strong authentication).
