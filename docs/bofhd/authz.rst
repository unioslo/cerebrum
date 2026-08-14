=======================
Authorization in bofhd
=======================

This document explains some details on how authorization is checked when a user
calls the ``bofhd_run_command`` remote procedure.

.. contents::
   :depth: 2
   :local:


Authentication
===============
Calls to ``bofhd_run_command`` must include a valid ``session_id``.  This
session-id is verified, and mapped to the *account-id* that fetched the
session-id in a previous ``bofhd_login`` call.

A ``Cerebrum.modules.bofhd.session.Session`` object is then passed as the first
argument to all command implementations.  This argument is usually called
*operator*.


Authorization
==============
Authorization checks are done by each *command implementation*.

The method that implements a command, will usually call a ``can_*`` method,
which is implemented by the ``authz``-attribute of the command class.  These
methods return ``True`` on success, and throws a ``PermissionDenied`` error on
failure.

Most ``can_*``-methods support an optional ``query_run_any``-method.  When this
is set to ``True``, we are in the `command listing`_ mode, and the method should
only return ``True`` or ``False`` to indicate whether a given user should *see*
the related commands in their clients.

Base authorization in bofhd is handled by the module
``Cerebrum.modules.bofhd.auth``.  The class ``BofhdAuth`` defines a number of
``can_*`` methods.

Different command classes will use different ``BofhdAuth`` subclasses for
authorization.  Some institutions will have their own "global" authorization
classes.  For these "global" classes to apply, the institution will also need:

1. A separate BofhdFooAuth-subclass, with the proper global auth class mixed in.
2. A separate BofhdFooCommand-subclass, with ``authz`` set to the custom
   BofhdFooAuth-class


Command listing
----------------
Clients will usually fetch a list of all available commands by calling the
``bofhd_get_commands`` remote procedure.

This will go through all available commands, and check whether they should be
included.  Commands may include a ``perm_filter`` which is used to omit the
command from listings if the user is not allowed to run the command with *any*
combination of arguments.

.. note::
   This is *not* an authorization check!  Commands are omitted to avoid
   cluttering up interactive clients with commands that the user will not be
   able to run!


Examples
---------
This is a minimal example to show a simple ``can_*`` authorization method could
be implemented and used:
::

    from Cerebrum.modules.bofhd import cmd_param
    from Cerebrum.modules.bofhd import errors
    from Cerebrum.modules.bofhd.auth import BofhdAuth
    from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase


    class FooAuth(BofhdAuth):

        def can_get_foo(self, operator_id, account=None, query_run_any=False):
            if query_run_any:
                # command listing mode (perm_filter checks) - no `account` is given.
                #
                # In this example - all authenticated users can see the command
                return True

            if self.is_superuser(operator_id):
                # superusers have no restrictions
                return True

            # authorization check - this requires an `account` to be given
            #
            # In this example, the operator can only see their own account data
            if account.account_id == operator_id:
                return True

            # Failed authorization checks raise a PermissionDenied error
            raise errors.PermissionDenied(
                "No access to account id=%s" %
                (account.account_id,)
            )


    class FooCommands(BofhdCommandBase):

        all_commands = {}
        authz = FooAuth

        all_commands['foo_get'] = cmd.Command(
            ("foo", "get"),
            cmd.AccountName(),
            perm_filter="can_get_foo",
        )

        def foo_get(self, operator, account_name):
            account = get_account_by_name(self.db, account_name)

            # The authorization check - will either raise a PermissionDenied
            # or return
            self.ba.can_get_foo(operator.get_entity_id(), account)

            # The rest of the command implementation


Most institutions have their own, global BofhdAuth implementation, which could
e.g. override the ``is_superuser`` implementation.  For this to apply to the
``FooAuth`` and ``FooCommands`` in the example above, the institution will need
a custom implementation with their own ``InstAuth`` class mixed in:
::

    class InstFooAuth(InstAuth, FooAuth):
        # mix in custom authorization class
        pass

    class InstFooCommands(FooCommands):
        # apply custom authorization class
        authz = InstFooAuth



BofhdAuth data model
=====================
To answer the various ``can_*`` questions, the auth module defines a
data model for storing access to given objects.  This data model is shown in
fig_auth_.

The model consists of:

operation (``_AuthRoleOpCode``)
    These are *constants* that each defines an abstract *operation*.

    The operations are typically various things that can be performed, such as
    ``set_password`` or ``create_user``.

opset (``BofhdAuthOpSet``)
    A group of operations.

    To grant permission to more than one operation at a time, a set of
    operations are grouped into an *opset*.  The opset is a list of operations,
    and each operation in the set can optionally have *attributes*
    that further restricts the operation.

    Opsets are typically defined in a config file, and regularly *imported* by
    ``contrib/permission_updates.py``.

target (``BofhdAuthOpTarget``)
    An abstract representation of an object, or a group of objects.

    These targets are the objects that an operation may be performed on.
    When granting permission to perform operations from an opset, it is always
    limited to a given *target*.

    There are two types of targets - global targets and specific targets.  The
    latter consists of a ``target_type`` and a ``target_entity_id``, and points
    to a given entity.  The former only consists of a ``target_type``, but does
    *not* refer to an entity.  These are used to e.g. grant access to *all*
    objects of a given type.

role (``BofhdAuthRole``)
    A role that has been given.

    Roles are given by the bofh command ``access grant``, and registers that a
    given *entity* (typically a group) has *access* to run operations from a
    given *opset* on a given *target*.

    Normally, the targets are *global targets*.  Individual operations may be
    restricted by operation attributes in the given opset.


The ``Cerebrum.modules.bofhd.auth`` contains more details on this data model.

.. _fig_auth :

.. figure:: ../figures/bofhd_auth.png
   :alt: an uml-diagram

   UML diagram of the bofhd authorization data model.
