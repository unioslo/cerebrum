""" Custom Jinja2 filters available to playbooks. """

import string
import os.path
from datetime import datetime


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


def dest(result):
    """ Take a result dict from a task, and looks for a `dest' keyword. """
    if isinstance(result, dict):
        result = result.get('results', [])
    if not isinstance(result, list):
        return None

    # We now have a results list
    if len(result) < 1:
        return None
    if len(result) > 1:
        return [dest([r, ]) for r in result]

    # One result
    result = result[0]
    return result.get('path', result.get('dest', None))


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

    """

    def filters(self):
        """ Return filters in this module. """
        return {
            'prefix': prefix,
            'postfix': postfix,
            'split': string.split,
            'tmpfile': tmpfile,
            'dest': dest,
        }
