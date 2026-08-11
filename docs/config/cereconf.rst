=========
cereconf
=========

``cereconf`` is the core configuration module of Cerebrum.

A ``cereconf`` module *must* be present (importable) for the core Cerebrum
functionality, as it defines how core classes should be built, as well as
providing database connection data.


Default config
==================
Settings are generally documented through comments in the default config,
``Cerebrum.default_config``.

All settings in ``Cerebrum.default_config`` must be present in the ``cereconf``
module.  It is customary to *import* all settings from the default config, and
just override the settings that needs to be changed:
::

    from Cerebrum.default_config import *  # noqa: F401, F403


Classes
========
The ``cereconf`` specifies which implementation to use for a range of core
classes.

All settings with a ``CLASS_``-prefix is a list or tuple of *base classes* to
use for the suffixed component.  E.g.:
::

    CLASS_DATABASE = ("Cerebrum.CLDatabase/CLDatabase",)
    CLASS_ACCOUNT = (
        "Cerebrum.modules.apikeys.mixins/ApiMappingAccountMixin",
        "Cerebrum.modules.Email/AccountEmailMixin",
        "Cerebrum.Account/Account",
        "Cerebrum.modules.bofhd.bofhd_mixins/BofhdAuthEntityMixin",
        "Cerebrum.modules.EntityTrait/EntityTrait",
        "Cerebrum.Entity/Entity",
    )


See ``Cerebrum.Utils.Factory`` for a full list of *components*.


Secrets
========
Most integrations requires some form of password, API key, or other secret in
order to connect or authenticate.

This is *usually* done by providing a secret through a *secret-lookup* (see
``Cerebrum.utils.secret``.

Legacy functionality and integrations looks for passwords in the ``DB_AUTH_DIR``
setting.  See ``Cerebrum.utils.secret`` for the naming scheme used for these
lookups.


Database
=========
Most Cerebrum functionality requires a database connection.  This is configured
through ``cereconf``:
::

    # Database wrapper class for postgres
    CLASS_DBDRIVER = ("Cerebrum.database.postgres/PsycoPG2",)

    # Connection data
    CEREBRUM_DATABASE_NAME = "example_db"
    CEREBRUM_DATABASE_CONNECT_DATA = {
        'user': "cerebrum_user",
        'host': "cerebrum-db.example.org",
    }
