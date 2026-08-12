====================
Cerebrum data model
====================

Cerebrum mostly consists of two main types of objects: the Constant_ and the
Entity_.


Constant
=========
Constants are pre-defined values that are stored in the database.

Constants are basically *enums* that live in the database, and typically
defines either a *data-type* (contact type, external id
type), or a unique value (e.g. authoritative systems, entity types, quarantines)

Constants are defined in collection classes, as an attribute in a
``Constants.ConstantsBase`` subclass, and are referred to by:

1. its attribute name (usually in code, where we require the constant to exist)
2. Its string value (usually from human input, or code if we're unsure if the
   constant exists)
3. Its generated, numeric value (database constraints, reverse lookup from
   database value)

Most tables that refer to a given constant, will do so by its generated id.


Entity
=======
``Cerebrum.Entity.Entity`` is the base class for all Cerebrum database objects.

It consists of a auto-generated, unique *entity id*, and a *entity type*.  The
latter is a constant_, used to group entities, and link them to a specific
entity subclass.

It is the core database object, and allows mixins and subclasses to *add*
information to the entity using its *entity id*.  In many ways, the Entity is
simply an *abstract object*.

Concrete information is added to entities using mixins_ and subclasses that
implement the `entity type`_.


Mixins
=======
Common object properties and features are typically implemented in *mixins*, for
re-use in a variety of Entity subclasses.

A simple example is the *EntityName* mixin, which adds support for unique names
for entities.  This mixin is typically used in the `entity type`_ implementation
of *groups* and *accounts*.


Entity type
============
Every distinct ``entity_type`` value is implemented in a specific subclass of
entity, with a *preset* selection of entity mixins.

One example is the ``Cerebrum.Group.Group``, which implements the ``group``
entity type.

Most entity types are also a Component_, which allows for additional features,
or alternative implementations of certain classes.


Component
==========
*Components* are classes that are dynamically built from configuration using the
Factory_.  By using components, we allow:

- Adding optional features through mixins
- Replacing the component implementation entirely

Typical components are: *Database*, *ChangeLog*, *Group*, *Account*


Factory
--------
Components are simply pre-defined class names that are fetched using the Factory
class.  All classes that are also *components* should normally be fetched from
the Factory, using its component name.

When creating, or working with e.g. a *Group*, the group class should be fetched
using ``Factory.get("Group")``:
::

    database_cls = Factory.get("Database")
    group_cls = Factory.get("Group")

    database = database_cls()
    group = group_cls(database)
    group.find_by_name("example")

    # do something with the example group


The actual group class can now be changed using the ``cereconf`` configuration
module (see :doc:`/config/cereconf`).  The group class in this example is
effectively:
::

    class _dynamic_group(bases):
        pass

… where ``bases`` are the classes specified in ``cereconf.CLASS_GROUP``.


The ``cereconf.CLASS_GROUP`` can be a single class, or a base class with mixins,
e.g.:
::

    # the base group class
    cereconf.CLASS_GROUP = [
        "Cerebrum.Group/Group",
    ]

    # some group subclass
    cereconf.CLASS_GROUP = [
        "Cerebrum.modules.foo.group/FooGroup",
    ]

    # a group (sub)class with mixins
    cereconf.CLASS_GROUP = [
        "Cerebrum.modules.entity_note.note_mixins/EntityNoteMixin",
        "Cerebrum.Entity/EntityQuarantine",
        "Cerebrum.Group/Group",
    ]
