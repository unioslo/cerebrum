"""
Cerebrum SQL file preprocessing utils.

This module contains the required functionality to pre-process the Cerebrum
sql-file format.  The format is just like SQL, but each regular SQL statement
must be prefixed by a metadata statement that categorizes the preceding
statement.

Metadata statements and phases
------------------------------
``category:metainfo``
    Sets a metadata variable.

    The following "statement" is not an SQL statement at all, but a metadata
    variable assignment. This is typically used to set a name and version for
    the sql file.

``category:main``
    Create a database element.

    The following statement typically creates a table, index, sequence or some
    other database structure. This phase is typically used to create database
    schemas.

``category:drop``
    Remove database structures.

    The following statement typically drops a table, index, sequence or some
    other database structure. This phase is typically used to remove some part
    of database schemas.

``category:main``
    Create database structures relating to constants.

    The following statement typically creates a table to host Cerebrum
    constants. This phase typically runs before the ``main`` phase, so that
    constants can be inserted into the database before the ``main`` phase runs.

    This is useful if the ``main`` phase refers to specific constants that must
    exist for its constraints.

``category:pre``
    Run pre-migration steps.

    The following statement typically creates a new database structure, alters
    some database structure, or creates a temporary database structure for
    migration.

``category:post``
    Run post-migration steps.

    The following statement typically cleans up anything temporary created by a
    ``pre``-phase, or drops obsolete database structures.

Each phase can optionally be suffixed by a database driver -- e.g.:
``category:main/Oracle`` is a statement for the ``main`` phase that should
*only* run if the database driver is *Oracle*.


Cerebrum design files
---------------------
There are two main types of Cerebrum SQL files:

Schema files
    Schema files are used with ``makedb.py`` to create the relevant database
    constructs.
    These files can be further separated into:

    - main schema files (i.e. core_tables.sql, bofhd_tables.sql,
      bofhd_auth.sql)
    - module schema files with optional features (e.g. mod_entity_trait.sql).

    When processing a file with ``makedb.py``, the following phases will be
    processed (in order):

    - code (create code tables)
    - (insert relevant cerebrum codes)
    - main
    - metadata

    Alternatively, if electing to drop schema files:

    - drop
    - metadata

Migration files
    Migration files are used with ``contrib/migrate_cerebrum_database.py`` to
    upgrade existing database constructs (e.g migrate_to_0_9_9.sql,
    migrate_to_bofhd_1_1.sql).

    Migrations are functions that optionally calls on ``makedb.py`` to run a
    specific phase of a specific file, so a given migration *could* run any
    phase in any order.

    Typically, a migration function will run the following phases:

    - pre
    - (insert codes)
    - (process migration)
    - metadata
    - post
"""
from __future__ import print_function

import io
import re
from distutils.version import StrictVersion


DEFAULT_ENCODING = 'utf-8'


# Tags: identifies meta-statements
#
# There is currently only one tag: 'category'.

TAG_CATEGORY = 'category'

VALID_TAGS = frozenset({
    TAG_CATEGORY,
})


# Phases: meta-statement filter
#
# Phases are categories of statements. When reading a cerebrum sql file, each
# statement must belong to a phase.

# metainfo phase: gather metadata
PHASE_METAINFO = 'metainfo'

# code phase: create code tables
PHASE_CODE = 'code'

# main phase: create schema
PHASE_MAIN = 'main'

# drop phase: drop schema
PHASE_DROP = 'drop'

# pre phase: pre-migration statements
PHASE_PRE = 'pre'

# post phase: post-migration statements
PHASE_POST = 'post'

VALID_PHASES = frozenset({
    PHASE_METAINFO,
    PHASE_MAIN,
    PHASE_DROP,
    PHASE_CODE,
    PHASE_PRE,
    PHASE_POST,
})


# Metainfo: metadata statements
#
# Metainfo are special statements that simply sets some metadata value.

# module name
METAINFO_NAME = 'name'

# module version
METAINFO_VERSION = 'version'

VALID_METAINFO = frozenset({
    METAINFO_NAME,
    METAINFO_VERSION,
})


# Find lines starting long comments: /*
RE_LONG_COMMENT_START = re.compile(r'\s*/\*', re.DOTALL)

# Find lines ending long comments: */
RE_LONG_COMMENT_STOP = re.compile(r'.*\*/', re.DOTALL)

# Find lines starting _and_ ending with long comment markers: /* ... */
RE_LONG_LINE_COMMENT = re.compile(r'\s*/\*.*\*/', re.DOTALL)

# Find lines with single line comments: -- ...
RE_LINE_COMMENT = re.compile(r'--.*')

# Find if line is ending a statement, i.e. ends with semi-colon.
# This is to know if the statement continues in the next line or not.
RE_SC_PAT = re.compile(r'.*;\s*')

# Find the end of a statement, i.e. semi-colon, to be able to remove it:
RE_SC_PAT_REPL = re.compile(r';\s*')

# Find any newlines:
RE_KILL_NEWLINE_REPL = re.compile(r'\n+')

# Find any whitespace. Used to remove any excess whitespace.
RE_KILL_SPACES_REPL = re.compile(r'\s+')


def parse_sql_file(filename, encoding=DEFAULT_ENCODING):
    """
    Parse an SQL definition file and return the statements and categories.

    Iterates through all lines in the file and generate statements from the
    lines. Comments are for instance filtered out.

    Note that the parser is somewhat limited. Long comments can for instance
    not be on the same line as SQL statements. Long comments have to start and
    stop on their own lines. Also, you can't stop and then start a new long
    comment on the same line.

    :type filename: str
    :param filename: a cerebrum sql file

    :type encoding: str
    :param encoding: encoding of the sql file

    :rtype: generator
    :return: an iterable of statements
    """
    is_inside_comment = False
    function_join_mode = False
    buffer_str = io.StringIO()

    def reset(buf):
        value = buf.getvalue().strip()
        buf.seek(0)
        buf.truncate()
        return value

    with io.open(filename, mode='r', encoding=encoding) as sqlfile:
        for lineno, line in enumerate(sqlfile, 1):

            line = RE_KILL_NEWLINE_REPL.sub(' ', line)
            line = RE_KILL_SPACES_REPL.sub(' ', line)

            # Ignore empty lines:
            if not line.strip():
                continue

            # Filter out lines with comments:
            if re.match(RE_LONG_LINE_COMMENT, line):
                is_inside_comment = False
                continue

            if re.match(RE_LONG_COMMENT_STOP, line):
                is_inside_comment = False
                continue

            if re.match(RE_LONG_COMMENT_START, line):
                is_inside_comment = True
                continue

            if is_inside_comment:
                continue

            if re.match(RE_LINE_COMMENT, line):
                continue

            upper_line = line.upper()

            # Handle functions correctly, as they might contain semi-colons
            if 'FUNCTION' in upper_line and 'DROP FUNCTION' not in upper_line:
                function_join_mode = True
                buffer_str.write(line)
            elif function_join_mode and 'LANGUAGE' in upper_line:
                function_join_mode = False
                buffer_str.write(RE_SC_PAT_REPL.sub('', line))
                yield reset(buffer_str)
            elif function_join_mode:
                buffer_str.write(line)
            else:
                # Handle everything else
                if RE_SC_PAT.match(line):
                    buffer_str.write(RE_SC_PAT_REPL.sub('', line))
                    yield reset(buffer_str)
                else:
                    buffer_str.write(line)


def parse_meta_statement(statement):
    """
    Parse a single cerebrum sql meta-statement.

    Each meta-statement consists of a tag, a phase, and an optional rdbms
    ('<tag>:<phase>[/<rdbms>]').

    >>> parse_meta_statement('category:metainfo')
    ('category', 'metainfo', None)
    >>> parse_meta_statement('category:main/Oracle')
    ('category', 'main', 'Oracle')

    :type statement: str

    :rtype: tuple
    :return: a tuple with (category, phase, rdbms)
    """
    tag, _, phase = statement.partition(':')

    if tag not in VALID_TAGS:
        raise ValueError("invalid tag %r (%r)" % (tag, statement))

    if '/' in phase:
        phase, _, rdbms = phase.partition('/')
    else:
        rdbms = None

    if phase not in VALID_PHASES:
        raise ValueError("invalid phase %r (%r)" % (phase, statement))

    return tag, phase, rdbms


def categorize(statements):
    """
    Categorize sql statements.

    In the Cerebrum SQL files, each statement is prefixed by a meta-statement.
    This function groups each statement together with a lexed meta-statement.

    :param statements:
        An iterable with statements.

        Typically this is the output from :py:func:`parse_sql_file`.

    :rtype: generator
    :return:
        An iterable that yields tuples that consists of:

        - tag (VALID_TAGS, i.e. 'category')
        - phase (VALID_PHASES, e.g. 'main', 'drop', 'code')
        - rdbms (e.g. 'Oracle')
        - statement (e.g. 'CREATE TABLE ...')
    """
    current_meta = None

    for stmt in statements:

        if not current_meta:
            # We require a meta-statement for each real statement
            current_meta = parse_meta_statement(stmt)
            continue

        category, phase, rdbms = current_meta
        yield category, phase, rdbms, stmt
        current_meta = None


def parse_metainfo(statement):
    """
    Parse a metainfo sql meta-statement.

    >>> parse_metainfo('name=foo')
    ('name', 'foo')
    >>> parse_metainfo('version=1.0')
    ('version', StrictVersion('1.0'))
    """
    key, _, value = statement.partition('=')
    key = key.strip()
    value = value.strip()
    if key not in VALID_METAINFO:
        raise ValueError("invalid metainfo key %r" % (key,))
    if key == METAINFO_VERSION:
        value = StrictVersion(value)
    return key, value


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='Create SQL file from a cerebrum design file',
        epilog=(
            'Note that the output SQL file may not be valid SQL, '
            'as it may contain Cerebrum-macros (eg. [:now])'
        ),
    )
    parser.add_argument(
        '--phase',
        dest='phases',
        action='append',
        choices=VALID_PHASES,
        help='only include the given phase (option may be repeated)',
    )
    parser.add_argument(
        'filename',
        help='a cerebrum design file',
    )
    args = parser.parse_args()

    def format_phase(category, phase, rdbms):
        if rdbms:
            return '-- {}:{}/{}'.format(category, phase, rdbms)
        else:
            return '-- {}:{}'.format(category, phase)

    def format_metadata(key, value):
        return '-- {} = {}'.format(key, value)

    items = categorize(parse_sql_file(args.filename))
    phases = set(args.phases or VALID_PHASES)

    curr_meta = None

    for category, phase, rdbms, stmt in items:
        if phase not in phases:
            # skip any phase not selected
            continue

        # output a metadata statement comment if the category/phase/rdbms tag
        # changes
        if curr_meta != (category, phase, rdbms):
            print(format_phase(category, phase, rdbms))
            curr_meta = (category, phase, rdbms)

        if phase == 'metainfo':
            # output metadata assignment as a comment
            key, value = parse_metainfo(stmt)
            value = format_metadata(key, value)
        else:
            value = stmt

        print('{}'.format(value))


if __name__ == '__main__':
    main()
