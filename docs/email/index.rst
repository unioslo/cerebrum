=========================
Email and email accounts
=========================

The ``Cerebrum.modules.Email`` module (along with ``design/mod_email``)
implements data models for storing information typically associated with an
email system.

.. todo:: Expand and refactor documentation on the Email module.

   As we add more info on the email module, the data model should
   probably be moved to its own document.

Model
=====
Most of the data model centers around the EmailTarget_, which represents an
abstract email account.  One-to-one relationships with EmailTargets are
typically EmailTarget subclasses, while many-to-one relationships are Entity
subclasses with an EmailTarget foreign key.


EmailTarget
-----------
EmailTargets are the *email accounts* in Cerebrum.

It is a common object that we can tie other email related data to.  It decides
how/where emails should be delivered.

Email targets are exposed in the email database LDAP_ tree, and used by the
email system to process incoming emails (e.g. bounce, deliver to inbox, forward
to address, forward to address AND deliver to inbox, forward to email list
system x, ...)

EmailTarget is backed by the ``email_target`` table.  This table references the
``entity_info`` table:

``entity_id``
    ``target_id`` in other tables

``entity_type``
    ``Constants.entity_email_target``

The other columns are:

``target_type``
    What *type* of email account this is: account, deleted, pipe, multi, etc...

``target_entity_id``, ``target_entity_type``
    Only applies to *some* target types.  These two attributes points to the
    *target* of the email account.  E.g. a regular email target
    (target_type=account) is owned by a user account.  In that case the target
    will be that user account.

    The multi target is a simplified email list function.  A multi target points
    to a group, and email to this target gets re-sent to all members of the
    group.

``email_target_using_uid``
    The posix uid of a user for this email target.  Only used when *executing*
    the pipe command for a pipe email target on the target host.

    .. todo:: Find out how ``email_target_using_uid`` is actually used.

``email_server_id``
    Points to an EmailServer_ that should handle this email target.


EmailDomain
-----------
Valid domain parts for email addresses managed by Cerebrum.  Each EmailDomain
should have an actual MX record in DNS.

In the ``entity_info`` table:

``entity_id``
    ``domain_id`` in other tables

``entity_type``
    ``Constants.entity_email_domain``

In the email domain table:

``domain``
    domain part of email addresses, (e.g. uio.no, usit.uio.no)

``description``
    description of usage for this domain


EmailAddress
------------
Actual email addresses managed by Cerebrum.

- Each address belongs to an EmailDomain_ (the domain part of the address)

- Each address must point to an EmailTarget_ (i.e. how should emails to this
  address be handled)

- Note that an adresses should generally not be deleted after being created.
  An email address should remain locked to its EmailTarget indefinitely, to
  prevent other EmailTargets from *re-using* that email address.

In the ``entity_info`` table:

``entity_id``
    ``address_id`` in other tables

``entity_type``
    ``Constants.entity_email_address``

In the address table:

``email_addr_local_part``
    The actual local part of an email address (e.g. ``example`` if the address
    is ``example@uio.no``)

``email_addr_domain_id``
    The domain part of an email address.  Points to an existing EmailDomain_.

``email_addr_target_id``
    The target (email account) of this address.  Points to an existing
    EmailTarget_.

``email_addr_expire_date``
    .. todo:: Find out if ``email_addr_expire_date`` is in use anywhere.


EntityEmailDomain
-----------------
Affiliation rules for email domains.

These are rule objects that stores which domains can/should be used by a person
with a given affiliation.

Commonly used as an OU mixin -> This OU ``entity_id`` has this ``affiliation`` to
``domain_id``

If no rule matches when creating a new account/email account, the user will
typically only get email addresses on the form ``<uid>@<default domain>``

``entity_email_domain_id``
    The target domain to use for a given *entity_id* and *affiliation*.

``entity_email_affiliation``
    *affiliation* filter (nullable).  Typically a given *affiliation* @ a given
    *OU* (entity_id) maps to a given *domain_id*.  A NULL value means that the
    entry functions as a *fallback* value when a given affiliation is *not*
    defined for this entity.


EmailQuota
----------
EmailTarget_ subclass to provide storage quotas for an email account.

Storage quotas are stored in Cerebrum, but exported to and enforced by the email
system.

.. todo:: Find out if quotas from Cerebrum are actually enforced.


EmailTargetFilter
-----------------
EmailTarget_ subclass to provide incoming email filter settings (i.e. which set
of filter rules to use, e.g. ``greylist``, ``uioonly``).


EmailSpamFilter
---------------
EmailTarget_ subclass with settings on what to do with emails that are filtered
(e.g. put in spam folder, drop all spam)


EmailVirusScan
--------------
EmailTarget_ subclass for virus scan settings.

The EmailVirusScan mixin is not actually in use anywhere.


EmailForward
------------
EmailTarget_ subclass with forwarding rules for email targets.

If a forward is set, all email to this target gets forwarded to the specified
address.  ``local_delivery`` controls whether forwarded emails are also
delivered/processed by the EmailTarget itself.

Note that a special ``EmailTarget.target_type`` exists for targets that should
*just* forward.


EmailVacation
-------------
EmailTarget_ subclass to provide autoreply for a limited time period.

.. todo:: Find out if anyone still uses EmailVacation (no longer in use @ UiO)


EmailPrimaryAddressTarget
-------------------------
EmailTarget_ subclass that designates a given `EmailAddress` as the *primary*
email address for this target.

Email targets can have multiple email addresses, but in some cases we need to
pick *one* address.

Most email targets have at least one address, and a primary email address set

Note: At UiO, the ``From`` address is typically modified to use this
address when sending emails from a personal account.


EmailServer
-----------
A server for handling email.

In the ``entity_info`` table:

``entity_id``
    ``server_id`` in email tables

``entity_type``
    .. todo:: Document entity_type for EmailServer.

.. todo:: Document how EmailServer works post-Exchange.


AccountEmailMixin
-----------------
Automatically maintains email info for an account.

.. todo:: Document AccountEmailMixin in more detail.


PersonEmailMixin
----------------
Allows listing email data for a person.

.. note:: Uses its own rules for determining primary account!

.. todo:: Document PersonEmailMixin in more detail.


Related functionality
=====================

bofhd
-----
``Cerebrum.modules.bofhd.bofhd_email`` implements commands for manually
modifying email targets and related email info.

.. todo:: Document the bofhd email commands in a separate document.


LDAP
-----
An LDAP tree with email target objects can be generated by
``contrib/generate_mail_ldif.py``.

.. todo:: Document email LDAP export in a separate document.
