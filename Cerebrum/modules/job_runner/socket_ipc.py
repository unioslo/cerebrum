# -*- coding: utf-8 -*-

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
""" Job Runner socket protocol. """
from __future__ import print_function

import json
import logging
import os
import signal
import socket
import threading
import time
from contextlib import closing

from six import text_type

import cereconf

from .times import to_seconds, fmt_asc, fmt_time


logger = logging.getLogger(__name__)


class SocketTimeout(Exception):
    """Raised by send_cmd() to interrupt a hanging socket call"""


def signal_timeout(signal, frame):
    logger.debug("signal_timeout(%r, %r)", signal, frame)
    raise SocketTimeout("timeout")


class SocketConnection(object):
    """ Simple socket reader/writer with buffer and size limit. """

    eof = b'\0'
    buffer_size = 1024 * 2
    max_size = 1024 * 128

    def __init__(self, sock):
        self._sock = sock

    def send(self, data):
        """ Send a null-terminated bytestring. """
        if self.eof in data:
            raise ValueError("payload cannot contain eof")
        data = data + self.eof
        if len(data) > self.max_size:
            raise ValueError("payload too large")
        totalsent = 0
        while totalsent < len(data):
            chunk = slice(totalsent,
                          min(len(data), totalsent + self.buffer_size))
            sent = self._sock.send(data[chunk])
            if sent == 0:
                raise RuntimeError("socket connection broken")
            totalsent = totalsent + sent
        return totalsent

    def recv(self):
        """ Receive a null-terminated bytestring. """
        chunks = []
        bytes_recd = 0
        while bytes_recd < self.max_size:
            chunk = self._sock.recv(min(self.max_size - bytes_recd,
                                        self.buffer_size))
            if chunk == b'':
                raise RuntimeError("socket connection broken")
            chunks.append(chunk.rstrip(self.eof))
            bytes_recd = bytes_recd + len(chunk)
            if chunk.endswith(self.eof):
                break
        return b''.join(chunks)


class Commands(object):
    """ A collection of commands. """

    def __init__(self):
        self.commands = {}

    def add(self, name, num_args=0):
        """ Add command

        :param str name: Command name
        :param int num_args: Expected number of arguments.
        """
        def wrapper(fn):
            fn.name = name
            fn.args = num_args
            self.commands[name] = fn
            return fn
        return wrapper

    def get(self, name):
        """ Get command from name. """
        try:
            return self.commands[name]
        except KeyError:
            raise ValueError("Invalid command: %r" % name)

    def check(self, name, arguments):
        """ Check that command name and argument list is valid. """
        command = self.get(name)
        if not command.args == len(arguments):
            raise ValueError("Invalid arguments: %r" % arguments)

    def parse(self, data):
        """ Turn data structure (list) into command and argument list. """
        try:
            name, arguments = data
            arguments = arguments or []
        except ValueError:
            raise ValueError("Invalid command: %r" % data)
        self.check(name, arguments)
        return self.get(name), arguments

    def build(self, name, arguments=None):
        """ Turn command into data structure (list). """
        arguments = arguments or []
        self.check(name, arguments)
        return [name, arguments]


class SocketProtocol(object):

    commands = Commands()

    def __init__(self, connection, job_runner):
        self.job_runner = job_runner
        self.connection = connection

    @property
    def job_queue(self):
        return self.job_runner.job_queue

    @classmethod
    def call(cls, connection, command, args):
        """ Send command, decode and return response. """
        raw_command = cls.commands.build(command, args)
        connection.send(json.dumps(raw_command))
        return json.loads(connection.recv())

    def handle(self):
        data = self.connection.recv()
        try:
            command, args = self.commands.parse(json.loads(data))
        except Exception as e:
            logger.warn("Unknown command", exc_info=True)
            self.respond("Unknown command: %s" % e)
        try:
            logger.info("Running %s", command.name)
            command(self, *args)
        except Exception as e:
            logger.error("Command failed: %r", command, exc_info=True)
            self.respond("Error: %s" % e)

    def respond(self, data):
        self.connection.send(json.dumps(data))

    @commands.add('RELOAD')
    def __reload(self):
        self.job_queue.reload_scheduled_jobs()
        self.job_runner.wake_runner_signal()
        self.respond('OK')

    @commands.add('QUIT')
    def __quit(self):
        self.job_runner.ready_to_run = ('quit',)
        self.respond('QUIT is now only entry in ready-to-run queue')
        self.job_runner.quit()

    @commands.add('KILL')
    def __kill(self):
        self.job_runner.queue_paused_at = time.time()
        self.job_runner.ready_to_run = ()
        self.respond('Initiating shutdown')
        self.job_runner.quit()

    @commands.add('PAUSE')
    def __pause(self):
        self.job_runner.queue_paused_at = time.time()
        self.respond('OK')

    @commands.add('RESUME')
    def __resume(self):
        self.job_runner.queue_paused_at = 0
        self.job_runner.wake_runner_signal()
        self.respond('OK')

    @commands.add('RUNJOB', num_args=2)
    def __runjob(self, jobname, with_deps):
        if jobname not in self.job_queue.get_known_jobs():
            self.respond('Unknown job %s' % jobname)
            return

        if with_deps:
            self.job_queue.insert_job(self.job_queue._run_queue, jobname)
            self.respond('Added %s to queue with dependencies' % jobname)
        else:
            self.job_queue.get_forced_run_queue().append(jobname)
            self.respond('Added %s to head of queue' % jobname)
        self.job_runner.wake_runner_signal()

    @commands.add('SHOWJOB', num_args=1)
    def __showjob(self, jobname):
        job = self.job_queue.get_known_jobs().get(jobname)
        started_at = self.job_queue._started_at.get(jobname)
        done_at = self.job_queue._last_run.get(jobname)
        if not job:
            self.respond('Unknown job %s' % jobname)
        else:
            ret = []
            if started_at:
                ret.append("Status: running, started at %s" %
                           fmt_asc(started_at))
            else:
                tmp = fmt_asc(done_at) if done_at else 'unknown'
                ret.append("Status: not running.  Last run: %s" % tmp)
                ret.append("Last exit status: %s" % job.last_exit_msg)
            ret.append("Executable command (may change!):"
                       " %s" % job.get_pretty_cmd())
            ret.append("Pre-jobs: %s" % job.pre)
            ret.append("Post-jobs: %s" % job.post)
            ret.append("Non-concurrent jobs: %s" % job.nonconcurrent)
            ret.append("When: %s, max-freq: %s" % (job.when, job.max_freq))
            if job.max_duration is not None:
                ret.append("Max duration: %s minutes" % (job.max_duration/60))
            else:
                ret.append("Max duration: %s" % (job.max_duration))
            self.respond('\n'.join(ret))

    @commands.add('STATUS')
    def __status(self):
        queue = self.job_queue
        sleep_to = self.job_runner.sleep_to
        paused_at = self.job_runner.queue_paused_at

        ret = "Run-queue: \n  %s\n" % "\n  ".join(
            (repr({
                'name': x['name'],
                'pid': x['pid'],
                'started': fmt_time(x['started']),
            }) for x in queue.get_running_jobs()))

        ret += 'Ready jobs: \n  %s\n' % "\n  ".join(
            (text_type(x) for x in queue.get_run_queue()))

        ret += 'Threads: \n  %s' % "\n  ".join(
            (repr(x) for x in threading.enumerate()))

        def fmt_job_times(job):
            fmt_last = fmt_dur = 'unknown'
            fmt_human = fmt_ago = ''

            last_run = queue._last_run[job]

            # debug
            if last_run:
                fmt_human = time.strftime(' (%F %T)', time.localtime(last_run))
            logger.debug("Last run of '%s' is '%s'%s",
                         job, last_run, fmt_human)

            if last_run:
                fmt_last = fmt_time(last_run)

            last_dur = queue._last_duration[job]
            if last_dur:
                fmt_dur = fmt_time(last_dur, local=False)

            if last_run:
                days = int((time.time() - last_run) / to_seconds(days=1))
                fmt_ago = "(%i days ago)" % days

            return '  '.join((fmt_last, fmt_dur, fmt_ago))

        ret += '\n%-35s %s\n' % ('Known jobs', '  Last run  Last duration')
        for job in sorted(queue.get_known_jobs()):
            ret += "  %-35s %s\n" % (job, fmt_job_times(job))

        if sleep_to:
            ret += 'Sleep to %s (%i seconds)\n' % (
                fmt_time(sleep_to),
                sleep_to - time.time())
        if paused_at:
            ret += "Notice: Queue paused for %s hours\n" % (
                fmt_time(time.time() - paused_at,
                         local=False))

        self.respond(ret)

    @commands.add('PING')
    def __ping(self):
        self.respond('PONG')


class SocketServer(object):

    def __init__(self):
        self._is_listening = False
        signal.signal(signal.SIGALRM, signal_timeout)

    def start_listener(self, job_runner):
        self.socket = socket.socket(socket.AF_UNIX)
        self.socket.bind(cereconf.JOB_RUNNER_SOCKET)
        self.socket.listen(1)
        self._is_listening = True
        while True:
            try:
                conn, _ = self.socket.accept()
            except socket.error:
                # "Interrupted system call" May happen occasionaly, Try again
                time.sleep(1)
                continue

            with closing(conn):
                context = SocketProtocol(SocketConnection(conn), job_runner)
                context.handle()

    def ping_server(self):
        try:
            os.stat(cereconf.JOB_RUNNER_SOCKET)
            if self.send_cmd("PING") == 'PONG':
                return True
        except socket.error:   # No server seems to be running
            print("WARNING: Removing stale socket")
            os.unlink(cereconf.JOB_RUNNER_SOCKET)
            return False
        except OSError:        # File didn't exist
            return False

    def cleanup(self):
        if not self._is_listening:
            return
        try:
            os.unlink(cereconf.JOB_RUNNER_SOCKET)
        except OSError:
            pass

    def __del__(self):
        self.cleanup()

    @classmethod
    def send_cmd(cls, command, args=None, timeout=2, jr_socket=None):
        """ Send command, decode and return response.

        Raises SocketTimeout if no response has come in timeout seconds.
        """
        jr_socket = jr_socket or cereconf.JOB_RUNNER_SOCKET
        args = args or []
        signal.signal(signal.SIGALRM, signal_timeout)
        signal.alarm(timeout)
        try:
            with closing(socket.socket(socket.AF_UNIX)) as sock:
                sock.connect(jr_socket)
                return SocketProtocol.call(SocketConnection(sock), command,
                                           args)
        finally:
            signal.alarm(0)
