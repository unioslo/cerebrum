#!/usr/bin/env python
#
# If the config variable is set, and exists as a folder under the templates
# directory, then any term (template name) that exists here will be used if it
# exists. If not, a template with the same name under the templates directory
# will be used in stead.
""" Ansible lookup plugin.

This Ansible lookup plugin looks up files or templates for a role.

The idea is to return files from 'templates' or 'files', but to allow the files
to be overloaded based on some configuration.

Usage:
    do_something_with_file: {{ item }}
    with_file_overload:
      - file: 'filename'      # The name of the file to look up. Mandatory.
      - base: 'files'         # The location where the file is found. Optional,
                              # default 'files'.
      - alt: 'alternate_dir'  # A sub-directory of 'base' that may or may not
                              # exist. Optional, default: None.
                              # If the 'alt' location exists, and contains
                              # 'file', then that file is used. Otherwise,
                              # we'll use 'file' from 'base', if that exists.
      - skip: no              # If the lookup should produce an erroneous
                              # return if the file is not found. If 'yes', the
                              # task will be skipped when no file is found.
                              # Optional, default: 'no'.

The lookup plugin will look for the filename 'file' somewhere in the 'base'
directory. The 'base' directory is relative to '<basedir>/../'.

If 'alt' is given, we will first look for the file in
'<basedir>/../<base>/<alt>'. If no 'alt' is given, or the file does not exist
in 'alt', then we will look for it in '<basedir>/../<base>'.

"""

import ansible.utils as utils
from ansible.errors import AnsibleError
from os.path import isfile, join, realpath


class LookupModule(object):

    """ Lookup implementation.

    Returns a list with one item. That item is either:
     + the first file that exists of:
       - <self.basedir>/../<base>/<alt>/<file>
       - <self.basedir>/../<base>/<file>

     + None if none of the files exist.

    """

    def __init__(self, basedir=None, **kwargs):
        # Basedir is typically ./files
        self.basedir = basedir

    def run(self, terms, inject=None, **kwargs):

        terms = utils.listify_lookup_plugin_terms(terms, self.basedir, inject)

        # Join args
        args = dict()
        for term in terms:
            if not isinstance(term, dict):
                raise AnsibleError(
                    "with_file_overload: Args must be key=value pairs")
            args.update(term)

        # Read out the args and defaults.
        alt = args.get('alt', None)
        base = args.get('base', 'files')
        file = args.get('file', '')
        skip = utils.boolean(args.get('skip', 'no'))

        # Validate the term types
        if not isinstance(base, basestring):
            raise AnsibleError(
                "with_file_overload: Illegal argument for base=%r" % base)
        if not isinstance(file, basestring):
            raise AnsibleError(
                "with_file_overload: Illegal argument for file=%r" % file)
        if not (alt is None or isinstance(alt, basestring)):
            raise AnsibleError(
                "with_file_overload: Illegal argument for alt=%r" % alt)

        def get_first(base, file, alt):
            """ Return the wanted file, or None if it doesn't exists. """
            base = realpath(join(self.basedir, '..', base))

            if alt and isfile(join(base, alt, file)):
                return join(base, alt, file)
            elif isfile(join(base, file)):
                return join(base, file)
            return None

        found = get_first(base, file, alt)
        if found:
            return [found, ]
        elif skip:
            return []
        return [None, ]
