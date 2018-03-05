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
import argparse
import imp
import importlib
import os
import sys


def import_file(filename, name):
    """ Imports a file as a given module. """
    # TODO: PY3 Not Python3 compatible
    module = imp.load_source(name, filename)
    sys.modules[name] = module
    return module


def import_module(name):
    """ Import a given module. """
    return importlib.import_module(name)


def reload_module(module):
    """ Module reload function that does not use PYTHONPATH. """
    name, filename = module.__name__, module.__file__

    # Strip .py[co], as reloading a .pyc doesn't really help us
    filename = os.path.splitext(filename)[0] + '.py'

    # Clear
    if name in sys.modules:
        del sys.modules[module.__name__]

    # Re-import
    if os.path.exists(filename):
        return import_file(filename, name)
    else:
        # Path changed?
        return import_module(name)


def get_job_config(name):
    if os.path.exists(name):
        return import_file(name, 'scheduled_jobs')
    else:
        return import_module(name)


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


def pretty_jobs_presenter(jobs, args):
    """Utility function to give a human readable presentation of the defined
    jobs. This should simulate job_runner's presentation, to be able to get the
    information in test, without having to run a real job_runner.

    To use the function, feed it with the jobs from a given scheduled_jobs.py.

    @type jobs: class Cerebrum.modules.job_runner.job_actions.Jobs
    @param jobs:
        A class with all the jobs to present. Normally the AllJobs class in a
        given scheduled_jobs.

    @type args: list
    @param args:
        Input arguments, typically sys.argv[1:]. This is to be able to present
        the jobs in different ways, without the need of much code in
        scheduled_jobs.py. Not implemented yet, but '--show-job' could for
        example be a candidate.

    """
    args = pretty_jobs_parser().parse_args(args)

    if args.list_jobs:
        for name in sorted(jobs.get_jobs()):
            print name

    elif args.show_job:
        jobname = args.show_job
        try:
            job = jobs.get_jobs()[jobname]
        except KeyError:
            print "No such job: %s" % jobname
            return
        print "Command: %s" % job.get_pretty_cmd()
        print "Pre-jobs: %s" % job.pre
        print "Post-jobs: %s" % job.post
        print "Non-concurrent jobs: %s" % job.nonconcurrent
        print "When: %s, max-freq: %s" % (job.when, job.max_freq)

    elif getattr(args, 'dump', False):
        # dumplevel = args[args.index('--dump') + 1]
        raise NotImplementedError("not implemented yet...")

    elif args.list_verbose:
        for name, job in sorted(jobs.get_jobs().iteritems()):
            print "Job: %s:" % name
            print "  Command: %s" % job.get_pretty_cmd()
            if job.pre:
                print "  Pre-jobs: %s" % job.pre
            if job.post:
                print "  Post-jobs: %s" % job.post
            if job.nonconcurrent:
                print "  Non-concurrent jobs: %s" % job.nonconcurrent
            print "  When: %s, max-freq: %s" % (job.when, job.max_freq)

    else:
        print "%d jobs defined" % len(jobs.get_jobs())
