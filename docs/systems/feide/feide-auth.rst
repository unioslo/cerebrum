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


Authentication using Entra
===========================
This method simply enables an existing integration between Feide and Azure/Entra.

The py:class:`Cerebrum.modules.no.OrgLDIF.NorEduAuthnLevelMixin` mixin adds this
authentication method to *all* Feide users.

Note that this method largely bypasses our quarantine rules, as we can no longer
remove/manipulate the ``userPassowrd`` attribute to prevent login.  One way to
remedy this, is to tag quarantined users with a given ``objectClass``, and
preventing Feide from seeing these users in LDAP (requires development + LDAP
configuration).


MFA with one time codes over SMS
================================
The py:class:`Cerebrum.modules.no.OrgLDIF.NorEduSmsAuthnMixin` mixin adds support for
using contact info as a valid MFA method in Feide.  Mobile phone numbers
registered with given person can be configured as valid SMS authentication
methods in Feide.

.. important::
   Cerebrum does not have any way of verifying mobile numbers for use as an MFA
   method.  This mixin should only be configured with source systems that verify
   *all* mobile numbers of the given type.

Configuration example to allow anyone with an affiliation of type
``AFFILIATION`` to receive one time codes over SMS to the phone number type
``TYPE`` from source system ``SOURCE``:
::

    LDAP_PERSON['norEduPersonAuthnMethod_selector'] = {
        'AFFILIATION': {
            ("SOURCE", "TYPE"): "optional label",
        },
    }

    # Use labels from the norEduPersonAuthnMethod_selector
    LDAP_PERSON['norEduPersonAuthnMethod_labels'] = True


The auth method shows up in Feide as:

    *One time code via SMS*
    Send a text message to <label>

If custom labels are enabled, and a label is given in the configuration, it
will be shown as-is.  If no label is set in the configuration, it will default
to "<TYPE> from <SOURCE>", e.g. "PRIVATE_MOBILE from SAP".

If custom labels are disabled, Feide will replace ``<label>`` with a partially
cencored phone number, e.g. ``********123``.


MFA with a TOTP authenticator
==============================
Cerebrum supports storing OTP secrets using asymmetric encryption.  These OTP
secrets can be formatted and exported to Feide as a valid authentication method
using the py:class:`Cerebrum.modules.otp.otp_ldif_utils.NorEduOtpMixin` mixin.

Pre-requisites
---------------
OTP database schema:
::

    python makedb.py design/mod_otp.sql

OTP mixins
    Constants + person mixin

    - ``CLASS_CONSTANTS += ("Cerebrum.modules.otp.constants/OtpConstants",)``
    - ``CLASS_CLCONSTANTS += ("Cerebrum.modules.otp.constants/OtpChangeTypeConstants",)``
    - ``CLASS_PERSON += (Cerebrum.modules.otp.mixins/OtpPersonMixin",)``


OTP policy setting
    An OTP policy dictates encryption schemes and storage formats for the
    default Cerebrum OTP secret.  For feide, this typically means:
    ::

        cereconf.OTP_POLICY = (
            "Cerebrum.modules.otp.otp_types/OtpTypeFeideJwe",
        )

    See the ``OtpTypeFeideJwe`` class for details.  This specific implementation
    will:

    - Create and store a (de-facto) standard Google Authenticator secret
    - Encrypt the secret for Feide, using a given public key in
      ``cereconf.DB_AUTH_DIR``.
    - Store the encrypted value as ``feide-ga``


OrgLDIF mixin
    The py:class:`Cerebrum.modules.otp.otp_ldif_utils.NorEduOtpMixin` will
    include otp secrets stored as ``feide-ga`` (the ``OtpTypeFeideJwe``
    default).


Setting OTP secrets
--------------------
Cerebrum has two methods for adding and removing otp secrets:

bofhd commands
    A default implementation in py:mod:`Cerebrum.modules.otp.bofhd_otp_cmds`
    lets superusers set, generate, or clear otp secrets.
    ::

        person otp_set person:<username>    # generate and set otp secret
        person otp_clear person:<username>  # remove the otp secret

        # generated otp secrets are stored temporarily in the operator session cache:
        person otp_session_list             # list all secrets (otp uris) generatedin the current session cache
        person otp_session_clear            # clear all secrets from the current otp session cache


API
    ``Cerebrum.rest.api`` includes endpoints that allows 3rd party applications
    (e.g.  passordtjenester) to set specific OTP secrets.
