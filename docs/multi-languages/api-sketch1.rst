==============================
Multiple language support API
==============================



Introduction
==============
This note describes the overall design of handling multiple languages in
Cerebrum. The primary motivation for this patch is to support various names
tagged with languages. We have an emerging need to process such data, and this
extension provides the necessary support in the API and the databasen schema.

The overall design has two distinct components -- language data handling for
constants and for entities (i.e. subclasses of ``_CerebrumCode`` and
``Entity``).


Constants
==========
Constant objects are fundamentally different from entities in that they do not
change and each constant used in Cerebrum has a corresponding Python
object. That is, there cannot be an update of any data related to a constant
without a corresponding update in the code. 

For these reasons, we opted to store language information for constants in the
code only. There is simply no reason to store anything language-related in the
database (it would complicate the database schema without yielding any
benefits). 

The code layout must be kept backward compatible, which means that any part of
Cerebrum NOT wishing to deal with constants' language data must be allowed to
ignore those parts of the API. For this reason, ``description`` field is still
kept (and it remains "untagged" wrt language). Although no longer technically
necessary, we would also keep the ``description`` column in the database to
make browsing constants easier (the description column is more human-friendly,
although unnecessary for the database schema).


Python code 
-------------
We have several constant classes, all inheriting from ``_CerebrumCode``.
Although the arguments may differ between classes, we can incorporate a
default argument with the language dictionary, so that language data could be
gradually introduced::

  system_fs = AuthoritativeSystem(
    "FS",   # <-- code_str parameter 
    "FS",   # <-- description parameter
    {"nb": "Felles StudentSystem",
     "en": "Unified Student Registry (FS)",})

  system_pbx = AuthoritativeSystem(
    "PBX", "PBX")

``system_fs`` has language data, while ``system_pbx`` does not. Both are
expected to work.

Additionally we need a number of constants representing various
languages. That's an additional class, just like any other constant type in
Cerebrum.


Language part of the API 
-------------------------
* ``_CerebrumCode.__init__()`` gets an additional ``lang=None``
  parameter. Constant classes wishing to register their respective names in
  various languages pass a dictionary from language codes to the name in that
  language. A subclass of ``_CerebrumCode`` must pass this parameter to
  ``_CerebrumCode.__init__()`` for initilization.
* ``code_str`` and ``description`` are accessible as they have always been. 
* Language strings are fetched via ``_CerebrumCode.lang(<lang code>)``. 
* If a constant is missing a name in a specific language, then ``lang()``
  returns the value of the ``description`` column/field. The idea (apart from
  easier the transition to multiple languages) is that it's better to provide
  some information in the wrong language than to return an empty string.
* ``str(<constant object>)`` (i.e. ``__str__()``) would still use
  ``description``. The entire code base will continue to work as before wrt
  constant "stringifying".

An additional point merits special attention. The dictionary argument with
language data passed to ``__init__`` is keyed by ``code_str`` attribute of
language constants::

  language_nb = LanguageCode("nb", "Bokmål")
  language_en = LanguageCode("en", "English")
  language_de = LanguageCode("de", "Deutsch")

  system_fs = AuthoritativeSystem(
    "FS", "FS", 
    {"nb": "Felles Studentsystem",
     "en": "Unified Student Registry (FS)",})

However, there is no mechanism prohibiting one to use *ANY* key (I am
uncertain whether such a check could be integrated without rewriting a
considerable part of constant bootstrapping; since languages themselves are
constants, checking for the 2-letter code correspondence with existing
constants requires that those constants already exist in the db. We *will* be
able to check improper language reference during usage, though). I.e. we won't
detect an improper language code during a constant definition. However, in
``_CerebrumCode.lang()`` there is actually a check on the argument, so that
strings are matched against actual ``LanguageCode`` constants.


Backward compatibility
-----------------------
Code that does not care about language data needs to specify neither the
constant description in various languages nor to use them in any
fashion. Constant objects' behaviour wrt ``int()`` and ``str()`` remains
unaltered. 


Database
---------
Strictly speaking, we no longer need the ``description`` column in the
database (to what end?). In the next iteration it may be sensible to move
the ``description`` column out of the database (the constant object remain
unchanged though, as seen from Python code).

Additionally, since we have a new constant type (languages), we need a table
for them as well. This has to be an integral part of the Cerebrum core.

There are no tables to migrate to start using constants with languages.


Examples
---------
And a sample run illustrating the new interface::

  >>> from Cerebrum.Utils import Factory
  >>> co = Factory.get("Constants")()
  >>> co.system_cached
  <_AuthoritativeSystemCode instance code_str='Cached' at 0x10997200>
  >>> str(_)
  'Cached'
  >>> co.system_cached.description
  'Internally cached data'
  >>> co.system_cached.lang("nb")
  'Internt cachede data'
  >>> co.system_cached.lang("en")
  'Internally cached data'
  >>> co.system_cached.lang(co.language_en)
  'Internally cached data'
  >>> co.system_cached.lang("de")
  'Internally cached data'
  >>> co.system_cached.lang("habla")
  Traceback (most recent call last):
    (...)
  Cerebrum.Errors.NotFoundError: Could not find: 
  {'int': None, '_lang': {}, '_desc': None, 'str': 'habla'}

The last line shows that using unknown codes fails. Also, note that if there
is no string specified for a specific language, one falls back to description
(this is the case with "de") -- it's better to have the message relayed in
some default language, than to fail.


Entity and subclasses
=======================
Short version: a new class similar to ``EntityName`` in interface and database
backing. 

Onto the somewhat longer version, then. We need to represent the following
tidbits in the database and offer a convenient interface. For each entity with
name-in-language, we record:

  - name data (the name itself)
  - corresponding language data (Bokmål, Nynorsk, English, etc)
  - corresponding name type (title, acronym, short name, etc)
  - (in the future) source system for the name-in-language.

We already have a template for such an interface in Cerebrum --
``EntityName``. ``EntityName`` by itself offers an interface to names
**unique** within a specific domain. Name-with-language needs do not not fit
this requirement, but the overall design can be reused.

For now there is no concept of name priorities. This is a possible extension
for the future. Nor is there a concept of source system for names (there are
simply no use cases for that at the moment, although it makes sense to
register that). That, too, could be added without disruptive changes to the
interface in the future.


Database
---------
As no table exists fitting the storage demands, ``entity_language_name`` has
been added to the core database schema.

Some of the name data would have to be migrated to this table.

For now we'll leave the source system out of the table, but that is a
potential candidate for next extension.


New API
--------
A new class, ``EntityNameWithLanguage`` becomes the interface to the
name-with-language data in Cerebrum. Such names are not required to be
unique. Nor is there a requirement to always have a specific name type in a
specific language (this may become an issue, though -- e.g. OUs used to always
have at least one non-NULL name).

The interface resembles that of ``EntityName``:

  * ``find_by_name_with_language``
  * ``add_name_with_language``
  * ``delete_name_with_language``
  * ``search_name_with_language``
  * ``get_name_with_language``
  * ``delete``

A class needing support for names in various language can inherit from
``EntityNameWithLanguage``. There is no ``populate`` step in this case --
names are registered/updated and deleted with ``add_name_with_language`` and
``delete_name_with_language`` respectively.


OU
---
OU/Stedkode is the first target of this migration: we need to support
organizational units' names in various languages. 


API changes
~~~~~~~~~~~~
Previously OU instances had a number of name attributes (``short_name``,
``name``, etc). These are no longer available. Name retrieval happens
through ``get_name_with_language``. However, in order to ease the transition
period, accessing these attributes is still allowed, albeit with a warning via
the logger framework (since such an access must have a language specified, the
default assumption is Norwegian bokmål).

As a consequence, the ``populate()``-interface has changed. Names are no
longer specified there (but rather added/modified via
``add_name_with_language``). Searching for OUs by name has also changed: any
by name lookup happens via
``search_name_with_language(entity_type=const.entity_ou)``. The ``ou_info``
table no longer has any name data recorded. Please note that adding a
name-with-language requires an existing ou_id. This means that for new OUs,
one would have to call ``write_db()`` before registering the very first name.

Removing name data has an additional challenge, since it's possible to leave
an OU nameless.


Data migration
~~~~~~~~~~~~~~~
We cannot allow OUs to lose names during data migration. Since the name
columns are dropped from the ``ou_info`` table, we need to move the data from
the columns to ``entity_language_name`` before dropping them.

Additionally, the authoritative source for OU data must supply the necessary
language data. If not, the exercise is somewhat pointless. Some of the code
has been adapted to the older usage pattern under the assumption that the
default language is Norwegian bokmål (not an unreasonable, but not necessarily
a correct assumption).


Example
~~~~~~~~ 
A sample snippet::

  >>> logger = Factory.get_logger("console")
  >>> ou.find(572)
  >>> ou.acronym
  WARNING Deprecated usage of OU: OU.acronym cannot be accessed directly. 
  Use get/add/delete_name_with_language
  'GT'
  <Cerebrum.Utils._dynamic_Constants object at 0x115297e8>
  >>> ou.get_name_with_language(co.ou_name_acronym, co.language_nb) 
  'GT'
  >>> ou.get_name_with_language(co.ou_name_acronym, co.language_de)
  Traceback (most recent call last):
  File "Cerebrum/Entity.py", line 628, in get_name_with_language
    self.const.LanguageCode(name_language)))
  Cerebrum.Errors.NotFoundError: Could not find: Entity id=572 has no name OU
  acronym in lang=de
  >>> ou.add_name_with_language(co.ou_name_acronym, co.language_nb, "GeTe")
  >>> ou.clear(); ou.find(572)
  >>> ou.get_name_with_language(co.ou_name_acronym, co.language_nb)  
  'GeTe'


Person
-------
One of the branch goals for Person entities is to support personal and work
titles in multiple languages. Unfortunately, ``Person`` class in itself
presents a couple of challenges. People in Cerebrum have essentially 2 kind of
names jammed into the same table -- proper human names and work/personal
titles. Conceptually, proper human names don't really have a language (at
least, they don't from any of the source systems we are using). Such a
division did not exist previously, as all person names were stored and
accessed in the same fashion.

Now there is a specific use case, and we want to support language information
for titles. The bare minimum is to move ``name_personal_title`` and
``name_work_title`` out of the ``person_name`` table (and change these
constants' type from ``_PersonNameCode`` to ``_EntityNameCode``).

Such a split will make it necessary to check the code for usage patterns
(and look for places where titles and names are mixed within the same API
calls). A review did not reveal any places where the name usage was
overlapping (typically we fiddle either with human names or with titles, with
a few exceptions).


API changes
~~~~~~~~~~~~
Person names are still accessed through the previously existing API. I.e. the
same procedure for retrieval and storage (plus the ``populate_name()`` magic)
for names (first, last and full). 

Titles, however, will be retrieved and stored through the
``EntityNameWithLanguage`` class.

For the sake of backward compatibility we could approach this differently. The
split in name/title-handling could be internalized to the API methods in
Person. It ought to be doable, but will be somewhat difficult for lookup
methods that allow specifying multiple name variants (we'll have to perform 2
separate db lookups and join the results depending on the name variants
specified).

This duality is likely to cause confusion in the future, so the next
appropriate step is to move all of people's names into
``entity_language_name``. That update, however, is for the next
iteration. 


Data migration
~~~~~~~~~~~~~~~
Migration is somewhat different here. With OUs we needed to move the name
data, whereas with personal titles we can simply drop them from the
database. Since no titles have been registered manually, this can be done
without any loss of data.

It would be easiest to migrate the schema if we rename the title constants in
the process (easiest to automate the transition), rather than delete
them. That is, ``Constants.py`` would still contain ``_PersonNameCodes`` for
titles, the data is migrated, and then the code base could be upgraded to a
version without ``name_personal_title`` and ``name_work_title``. I.e. the
migration process runs thusly:

  #. update the code base.
  #. DELETE * from person_name WHERE name_variant in (...) (part of the schema
     migration)
  #. update Constants.py (remove ``name_personal_title`` etc).

Following that, we can run whichever job processes titles to populate the
``entity_language_name`` table.


Example
~~~~~~~~
>>> p.find(20905)
>>> [x for x in p.get_names() if x["name_variant"] not in
    (co.name_first, co.name_last, co.name_full)]
[]
>>> p.add_name_with_language(co.work_title, co.language_en, "Ruler of the world")
>>> [x for x in p.get_names() if x["name_variant"] not in
... (co.name_first, co.name_last, co.name_full)]
[]
>>> p.search_name_with_language(entity_id=p.entity_id)
[(20905L, 102L, 835L, 824L, 'Ruler of the world'), 
 (20905L, 102L, 835L, 826L, 'Overingeni\xf8r'), 
 (20905L, 102L, 835L, 827L, 'Overingeni\xf8r'), 
 (20905L, 102L, 840L, 827L, 'Overingeni\xf8r'),
 (20905L, 102L, 840L, 826L, 'Overingeni\xf8r'),]
>>> p.get_name_with_language(co.work_title, co.language_nb)
'Overingeniør'
>>> p.get_name_with_language(co.work_title, co.language_en)
'Ruler of the world'
>>> db.rollback() 
>>> p.get_name_with_language(co.work_title, co.language_en)
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "Cerebrum/Entity.py", line 628, in get_name_with_language
Cerebrum.Errors.NotFoundError: Could not find: 
Entity id=20905 has no name WORKTITLE in lang=en
>>> print p.get_name_with_language(co.work_title, co.language_en, default=None)
None



Code/schema migration
========================
All the migration magic is located in
``contrib/migrate_cerebrum_database.py``. There is essentially one new table
and a bit of data shuffling between ``ou_info`` and
``entity_language_name``. 

**WARNING**! Before using this patch in a production environment, make sure
that the import routines do, in fact, fetch OU names and person titles and tag
them with languages. 

Migration itself:

 #. Update the source tree::

      svn up

 #. Check the current schema version::

      $ python contrib/migrate_cerebrum_database.py --info
      Your current db-version is: 0.9.15
      (...)

 #. Migrate the database::

      python contrib/migrate_cerebrum_database.py \
             --from rel_0_9_15 --to rel_0_9_16 \
             --makedb-path $(pwd) \
             --design-path $(pwd)/design

    This will create the new tables, move OU names and drop person titles.

 #. (optional) svn up Constants.py (upgrade to the latest version of
    Constants.py, which does not have ``person_name_title`` and friends).

 #. Run OU import and person import to fetch new titles.


List of files
~~~~~~~~~~~~~~
The patch is pretty large. An diff between trunk and branch can be fetched
thusly::

  $ svn diff --summarize \
        'https://cerebrum.svn.sourceforge.net/svnroot/cerebrum/trunk/cerebrum' \
        'https://cerebrum.svn.sourceforge.net/svnroot/cerebrum/branches/cerebrum-multi-language'

Most of the changes are trivial. But do take a look.

List of tested scripts, files, etc:

  - generate_org_ldif.py
  - uio/import_OU.py
  - uio/import_HR_person.py
  - contrib/generate_name_dictionary.py
  - contrib/no/uio/generate_frida_export.py
  - Cerebrum/modules/no/uio/bofhd_uio_cmds.py
  - contrib/no/hia/import_FS.py   
  - contrib/no/hia/import_SAP_person.py
  - Cerebrum/modules/no/hia/bofhd_hia_newcmds.py


Future work
============
* Does db_clean.py needs fixing for new change_log event usage.

* How do we deal with this use case: "Give me a name of <this type>, I don't
  care about the language"? What if there are multiple languages matching? Do
  we want a deterministic behaviour in such cases?

* How do we delete OU names during import? That is, assuming an OU which is no
  longer active, do we leave its names alone? Or are they removed from the
  db?

* Add source system to ``entity_language_name``? For now, there are no use
  cases where it is needed, but it's obviously a useful (and potentially
  necessary) extension.

* Tag ``_EntityNameCode`` with entity type they are applicable to. This would
  allow us to create schema constraints that prevent assigning wrong name
  codes (i.e. assigning ``ou_name_acronym`` to a Person instance).

* There is a potential overlap in functionality between
  ``entity_language_name`` and
  ``mod_employment:person_employment.description``. This should be addressed
  (``description`` does not necessary specify a title, but it is, in fact,
  used as such).
