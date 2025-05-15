# -*- coding: utf-8 -*-
#
# Copyright 2007-2025 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
"""
Default `file_clean_conf` module.

This config is intended for use with ``contrib/utils/file-cleaner.py``.  Note
that the legacy ``contrib/file_clean.py`` also use this config file, but
expects different settings.  Only one of these should be set up to run in a
given environment.

Be careful: Nothing prevents you from creating two conflicting entries (e.g.
two sets of params that operate on the same `dirname`).

Settings
--------
The following settings apply to both ARCHIVE_FILES and DELETE_FILES entries:

``dirname``
    Directory with files or subdirectories to either delete or archive.

    Note that there's no recursion, allthough subdirectories may get archived
    or deleted when working with ``file_type = "dir"``.

``file_type``
    Either "file" or "dir".  Will only match entries in *dirname* of this type.

``pattern``
    This is a regex pattern for selecting files or directories within *subdir*
    to archive or delete.

    Caveats: You should add a trailing '$' to prevent matching archives or
    other unintended entries.  Matching a literal '$' at the end of the pattern
    may cause some problems when cleaning up archives.

``delete_age``
    How many days to keep matching files (or archives in archive mode).

    Setting this value to 0 has different behaviour in our two modes:

    - in archive mode it will prevent archive cleanup
    - in delete mode it will delete matches regardless of age


And the following settings only apply to ARCHIVE_FILES entries:

``archive_dir``
    A directory to place archives in.  The default (None) will use *dirname* as
    the archive directory.

``archive_age``
    Number of days to wait before archiving a file or directory.  Only entries
    that are at least `archive_age` days old will be archived.  Set to 0 to
    archive files regardless of age.

``keep_originals``
    Set to `True` to keep the input files after they have been archived.

    The default (False) will delete the input entries, and only keep the
    archived copy.

``archive_combo``
    Prefix for a combined archive.

    If this is set, all matching entries in *dirname* will be placed in a
    single archive file.  The default (empty value) will create one archive for
    each matching entry.

``archive_replace``
    Replace/overwrite archives if they exist.

    The naming scheme for archives (``<source-entry> + [.tar].gz`` or
    ``<archive-combo> + <date> + .tar.gz``) may cause a naming conflict.
    This can especially happen if the cleanup runs multiple times a day, and/or
    the ``keep_originals`` setting is enabled.

    If set to ``True``, the new archive will replace the exising archive in
    these cases.

    If set to ``False``, the new archive filename may get an additional counter
    suffix to prevent collisions.
"""

#
# Files and folders to archive.
#
# Note that the behaviour of `delete_age` here works differently from the
# DELETE_FILES setting.  If `delete_age` is set to 0 (or lower), archive
# deletion is disabled.
#
# Examples:
#
#     ARCHIVE_FILES = [
#         # Compress logs in-place
#         {
#             # Find all files in /path/to/api-logs named e.g. log-2025-04-15
#             'dirname': "/path/to/api-logs/",
#             'pattern': r"log-\d+-\d+-\d+",
#             'file_type': "file",
#
#             # Delay archiving by 3 days, keep archived logs for 180 days
#             'archive_age': 3,
#             'delete_age': 180,
#
#             # Delete input files, only keeping the compressed copy
#             # 'keep_originals': False,
#
#             # Don't replace exising archives in case of naming conflicts.
#             # This shouldn't happen, though.
#             # 'archive_replace': False,
#         },
#
#         # Daily backup of certain files
#         #
#         # This is useful e.g. if we do a daily `scp` of import files from
#         # some remote location
#         {
#             'dirname': "/path/to/fs-files/",
#             'file_type': "file",
#             'pattern': r".*\.xml",
#
#             # Put archives in a archive/ subdirectory
#             'archive_dir': "/path/to/fs-files/archive/",
#
#             # Archive all matching files, keep archives for 14 days
#             'archive_age': 0,
#             'delete_age': 14,
#
#             # Keep the original input files, as we always want the latest set
#             # available.
#             'keep_originals': True,
#
#             # Create a single archive with all the matching files
#             # (``fs-archive-<iso-date>.tar.gz``)
#             'archive_combo': "fs-archive",
#
#             # Replace archive in case of naming conflicts.
#             'archive_replace': True,
#
#         }
#     ]
#
ARCHIVE_FILES = []


#
# Files and folders to delete
#
# Note that the behaviour of `delete_age` here works different from the
# ARCHIVE_FILES setting.  If `delete_age` is set to 0 (or lower), all matching
# files are deleted, regardless of age.
#
# Examples:
#
#     DELETE_FILES = [
#         # Remove old, print jobs created by bofhd after 14 days
#         {
#             'dirname': "/path/to/spool-dir/",
#             'name_pattern': r"bofh_spool.*",
#             'file_type': "dir",
#             'min_age': 14,
#         },
#
#         # Remove debug files created by
#         # `contrib/no/dfo/fetch-employee-data.py` after 30 days
#         {
#             'dirname': "/path/to/dfo-dumps/",
#             'name_pattern': r"dump-\d+-\d+-\d+\.json",
#             'file_type': "file",
#             'min_age': 30,
#         }
#     ]
#
DELETE_FILES = []
