# -*- coding: utf-8 -*-
""" Custom Jinja2 filters available to playbooks. """

import string
import os.path
from datetime import datetime
from ansible import errors


def prefix(input, pre):
    """ Prefix `input' with `pre'.

    :type input: basestring or list
    :param input:
        A string or list of strings to prepend with `pre'

    :type pre: basestring
    :param pre:
        A string to prepend to `input'

    :rtype: basestring or list
    :return:
        Returns a string or list of strings, prepended with `pre'.

    """
    if isinstance(input, list):
        for i, val in enumerate(input):
            input[i] = prefix(val, pre)
        return input

    if not isinstance(input, basestring):
        input = str(input)
    return (pre + input)


def postfix(input, post):
    """ Prefix `input' with `pre'.

    :type input: basestring or list
    :param input:
        A string or list of strings to append with `post'

    :type post: basestring
    :param post:
        A string to append to `input'

    :rtype: basestring or list
    :return:
        Returns a string or list of strings, appended with `post'.

    """
    if isinstance(input, list):
        for i, val in enumerate(input):
            input[i] = prefix(val, post)
        return input

    if not isinstance(input, basestring):
        input = str(input)
    return (input + post)


def _result_key(register, key, filter_name):
    """ Filter out a given key from a registered result variable.

    :param dict register: The result of a task `register' keyword.
    :param str key: A dict key to look for.
    :param str filter_name: Name of the caller filter, for errors.

    :returns list: A list containing one or more results.

    :raises AnsibleFilterError: If an invalid dict is given as input

    """

    if type(register) != dict:
        raise errors.AnsibleFilterError("|%s expects a dictionary" %
                                        filter_name)

    # ONE key, directly in the register dict
    if key in register:
        return [register.get(key), ]
    elif 'results' in register:
        # A list of result dicts, in a list under the 'results' key
        return filter(lambda x: x is not None,
                      [x.get(key) for x in register.get('results')])
    raise errors.AnsibleFilterError("|%s expects a dictionary with '%s'" %
                                    (filter_name, key))


def stdout(register):
    """ Filter stdout from result.

    Get a string of one or more stdout values from a dict produced by the
    `register' task keyword.

    :param dict register: The result of a task `register' keyword.

    :returns str: A string of stdout messages.

    """
    out = _result_key(register, 'stdout', 'stdout')
    return u'\n\n'.join([x.strip() for x in out])


def stderr(register):
    """ Filter stderr from result.

    Get a string of one or more stderr values from a dict produced by the
    `register' task keyword.

    :param dict register: The result of a task `register' keyword.

    :returns str: A string of stderr messages.

    """
    out = _result_key(register, 'stderr', 'stderr')
    return u'\n\n'.join([x.strip() for x in out])


def rc_or(register):
    """ An `OR' of all found return codes.

    Get an `OR'-ed value of one or more rc values from a dict produced by the
    `register' task keyword.

    :param dict register: The result of a task `register' keyword.

    :returns int: A combination of all return codes

    """
    out = _result_key(register, 'rc', 'rc_or')
    rc = 0
    for c in out:
        rc |= int(c)
    return rc


def tmpfile(filename, prefix='ansible-', remote_tmp='/tmp'):
    """ Generate a temporary remote filename to use.

    Given a filename string `/path/to/something.ext', this filter should
    generate a new string `<remote_tmp>/<prefix>something_<us>.ext',
    where `<remote_tmp>' is the ansible setting of the same name, prefix is an
    optional argument, and <us> is hex(timestamp in microseconds) of when the
    filter is called.

    The returned string has a high likelyhood of being an available filename
    for temporary use on the remote host.

    """
    base, ext = os.path.splitext(os.path.basename(filename))
    us = int(datetime.now().strftime('%s%f'))
    return os.path.join(
        remote_tmp,
        "%s%s_%x%s" % (prefix, base, us, ext))


def dest(register):
    """ Filter destination from a result.

    Get the 'dest' or 'path' value from a dict procuded by the `register' task
    keyword.

    :param dict register: The result of a task `register' keyword.

    :returns str: The found destination

    :raise AnsibleFilterError:
        If no destination is found, multiple destinations are found, or if the
        input is not a proper result dict.

    """
    for word in ('dest', 'path', ):
        out = _result_key(register, word, 'dest')
        if len(out) == 1:
            return out[0]  # Found dest, return result
        if len(out) == 0:
            continue  # Didn't find, try next keyword
        # Found multiple, don't know what to return!
        raise errors.AnsibleFilterError("|dest found multiple destinations")

    # Didn't find any of the keywords
    raise errors.AnsibleFilterError("|dest found no destination")


class FilterModule(object):

    """ Custom filter module.

    Filters
    -------

    prefix:
        Prefix a string or list of strings with a set prefix.
    postfix:
        Postfix a string or list of strings with a set postfix
    split:
        Split a string into a list (string.split)
    tmpfile:
        Generate a remote tmp filename in the `remote_tmp' folder
    dest:
        Parse the `dest' value from a `template' or `copy' task result
    stdout:
        Parse and join the `stdout' value from a command task
    stderr:
        Parse and join the `stdout' value from a command task
    rc:
        Parse and OR the `rc' value from a command task

    """

    def filters(self):
        """ Return filters in this module. """
        return {
            'prefix': prefix,
            'postfix': postfix,
            'split': string.split,
            'tmpfile': tmpfile,
            'dest': dest,
            'stdout': stdout,
            'stderr': stderr,
            'rc_or': rc_or,
        }
