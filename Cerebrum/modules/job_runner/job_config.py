# -*- coding: utf-8 -*-
#
# Copyright 2018 University of Oslo, Norway
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
""" Job Runner job configuration. """
from __future__ import print_function

import argparse
import imp
import importlib
import os
import sys

from .times import fmt_time


DEFAULT_MODULE_NAME = 'scheduled_jobs'
DEFAULT_JOB_CLASS = 'AllJobs'


def _import_file(filename, name):
    """ Imports a file as a given module. """
    # TODO: PY3 Not Python3 compatible
    #       We do this a bit in cerebrum, maybe make some importlib utils?
    module = imp.load_source(name, filename)
    sys.modules[name] = module
    return module


def _import_module(name):
    """ Import a given module. """
    return importlib.import_module(name)


def reload_job_config(module):
    """ Module reload function that does not use PYTHONPATH. """
    name, filename = module.__name__, module.__file__

    # Strip .py[co], as reloading a .pyc doesn't really help us
    filename = os.path.splitext(filename)[0] + '.py'

    # Re-import
    if os.path.exists(filename):
        module = _import_file(filename, name)
    else:
        # Path changed?
        module = _import_module(name)
    return module


def get_job_config(name):
    if os.path.exists(name):
        module = _import_file(name, DEFAULT_MODULE_NAME)
    else:
        module = _import_module(name)
    return module


def pretty_jobs_parser():
    parser = argparse.ArgumentParser(
        description="Show stuff in this job runner config")

    action = parser.add_mutually_exclusive_group()

    action.add_argument(
        '-l', '--list',
        dest='list_jobs',
        action='store_true',
        default=False,
        help="List all the jobs")

    action.add_argument(
        '-v', '--list-verbose',
        dest='list_verbose',
        action='store_true',
        default=False,
        help="List jobs verbosely")

    # action.add_argument(
    #     '--dump',
    #     action='store_true',
    #     default=False,
    #     help='Dump jobs?')

    action.add_argument(
        '-s', '--show-job',
        dest='show_job',
        metavar="NAME",
        help="Show a given job %(metavar)s")

    return parser


def _pretty_jobs_presenter(jobs, args):
    """ Print a human readable presentation of a collection of jobs.

    This should simulate job_runner's presentation, to be able to get the
    information in test, without having to run a real job_runner.

    :type jobs: class Cerebrum.modules.job_runner.job_actions.Jobs
    :param jobs:
        A class with all the jobs to present. Normally the AllJobs class in a
        given scheduled_jobs.

    :type args: argparse.Namespace
    :param args: Options on what to print (result of pretty_jobs_parser).

    """
    if args.list_jobs:
        for name in sorted(jobs.get_jobs()):
            print(name)

    elif args.show_job:
        jobname = args.show_job
        try:
            job = jobs.get_jobs()[jobname]
        except KeyError:
            print("No such job: %s" % jobname)
            return
        print("Command: %s" % job.get_pretty_cmd())
        print("Pre-jobs: %s" % job.pre)
        print("Post-jobs: %s" % job.post)
        print("Non-concurrent jobs: %s" % job.nonconcurrent)
        print("When: %s, max-freq: %s" % (job.when, job.max_freq))

    elif getattr(args, 'dump', False):
        # dumplevel = args[args.index('--dump') + 1]
        raise NotImplementedError("not implemented yet...")

    elif args.list_verbose:
        for name, job in sorted(jobs.get_jobs().iteritems()):
            print("Job: %s:" % name)
            print("  Command: %s" % job.get_pretty_cmd())
            if job.pre:
                print("  Pre-jobs: %s" % job.pre)
            if job.post:
                print("  Post-jobs: %s" % job.post)
            if job.nonconcurrent:
                print("  Non-concurrent jobs: %s" % job.nonconcurrent)
            print("  When: %s, max-freq: %s" % (job.when, job.max_freq))

    else:
        print("%d jobs defined" % len(jobs.get_jobs()))


def pretty_jobs_presenter(jobs, args):
    """ Compability function, should be compatible with old configs. """
    args = pretty_jobs_parser().parse_args(args)
    return _pretty_jobs_presenter(jobs, args)


def dump_jobs(scheduled_jobs, details=0):
    """ The job_runner implementation of --dump-jobs. """
    jobs = scheduled_jobs.get_jobs()
    shown = {}

    def dump(name, indent):
        info = []
        if details > 0:
            if jobs[name].when:
                info.append(str(jobs[name].when))
        if details > 1:
            if jobs[name].max_freq:
                info.append(
                    "max_freq=%s" % fmt_time(jobs[name].max_freq, local=False))
        if details > 2:
            if jobs[name].pre:
                info.append("pre=%s" % repr(jobs[name].pre))
            if jobs[name].post:
                info.append("post=%s" % repr(jobs[name].post))
        print("%-40s %s" % ("   " * indent + name, ", ".join(info)))
        shown[name] = True
        for k in jobs[name].pre or ():
            dump(k, indent + 2)
        for k in jobs[name].post or ():
            dump(k, indent + 2)
    keys = jobs.keys()
    keys.sort()
    for k in keys:
        if jobs[k].when is None:
            continue
        dump(k, 0)
    print("Never run: \n%s" % "\n".join(
        ["  %s" % k for k in jobs.keys() if k not in shown]))


# python -m Cerebrum.modules.job_runner.job_config

def main(args=None):
    parser = pretty_jobs_parser()
    parser.add_argument(
        '--config',
        dest='config',
        metavar='NAME',
        default=DEFAULT_MODULE_NAME,
        help='A python module (or file) with jobs')
    parser.add_argument(
        '--jobs',
        dest='config_attr',
        default=DEFAULT_JOB_CLASS,
        help="The config attribute that contains jobs")

    args = parser.parse_args(args)
    config = get_job_config(args.config)
    all_jobs = getattr(config, args.config_attr)
    _pretty_jobs_presenter(all_jobs(), args)


if __name__ == '__main__':
    main()
