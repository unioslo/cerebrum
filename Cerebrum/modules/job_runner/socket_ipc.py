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
import logging
import os
import signal
import socket
import threading
import time

import cereconf

from .times import to_seconds


logger = logging.getLogger(__name__)


class SocketHandling(object):
    """Simple class for handling client and server communication to
    job_runner"""

    class Timeout(Exception):
        """Raised by send_cmd() to interrupt a hanging socket call"""
        pass

    @classmethod
    def timeout(cls, sig, frame):
        raise cls.Timeout("Timeout")

    def __init__(self):
        self._is_listening = False
        signal.signal(signal.SIGALRM, type(self).timeout)

    def _format_time(self, t):
        if t:
            return time.asctime(time.localtime(t))
        return None

    def _show_job(self, jobname, job_runner):
        job = job_runner.job_queue.get_known_jobs().get(
            jobname, None)
        if not job:
            return 'Unknown job %s' % jobname

        tmp = self._format_time(job_runner.job_queue._started_at.get(jobname))
        if tmp:
            ret = "Status: running, started at %s\n" % tmp
        else:
            tmp = self._format_time(
                job_runner.job_queue._last_run.get(jobname))
            ret = "Status: not running.  Last run: %s\n" % tmp or 'unknown'
            ret += "Last exit status: %s\n" % job.last_exit_msg
        ret += "Command: %s\n" % job.get_pretty_cmd()
        ret += "Pre-jobs: %s\n" % job.pre
        ret += "Post-jobs: %s\n" % job.post
        ret += "Non-concurrent jobs: %s\n" % job.nonconcurrent
        ret += "When: %s, max-freq: %s\n" % (job.when, job.max_freq)
        if job.max_duration is not None:
            ret += "Max duration: %s minutes\n" % (job.max_duration/60)
        else:
            ret += "Max duration: %s\n" % (job.max_duration)
        return ret

    def start_listener(self, job_runner):
        self.socket = socket.socket(socket.AF_UNIX)
        self.socket.bind(cereconf.JOB_RUNNER_SOCKET)
        self.socket.listen(1)
        self._is_listening = True
        while True:
            try:
                conn, addr = self.socket.accept()
            except socket.error:
                # "Interrupted system call" May happen occasionaly, Try again
                time.sleep(1)
                continue
            while 1:
                data = conn.recv(1024).strip()
                if data == 'RELOAD':
                    job_runner.job_queue.reload_scheduled_jobs()
                    job_runner.wake_runner_signal()
                    self.send_response(conn, 'OK')
                    break
                elif data == 'QUIT':
                    job_runner.ready_to_run = ('quit',)
                    self.send_response(
                        conn, 'QUIT is now only entry in ready-to-run queue')
                    job_runner.quit()
                    break
                elif data == 'KILL':
                    job_runner.queue_paused_at = time.time()
                    job_runner.ready_to_run = ()
                    self.send_response(
                        conn, 'Initiating shutdown')
                    job_runner.quit()
                    break
                elif data == 'PAUSE':
                    job_runner.queue_paused_at = time.time()
                    self.send_response(conn, 'OK')
                    break
                elif data == 'RESUME':
                    job_runner.queue_paused_at = 0
                    job_runner.wake_runner_signal()
                    self.send_response(conn, 'OK')
                    break
                elif data.startswith('RUNJOB '):
                    jobname, with_deps = data[7:].split()
                    with_deps = bool(int(with_deps))
                    if jobname not in job_runner.job_queue.get_known_jobs():
                        self.send_response(conn, 'Unknown job %s' % jobname)
                    else:
                        if with_deps:
                            job_runner.job_queue.insert_job(
                                job_runner.job_queue._run_queue, jobname)
                            self.send_response(
                                conn,
                                'Added %s to queue with dependencies'
                                % jobname)
                        else:
                            job_runner.job_queue.get_forced_run_queue().append(
                                jobname)
                            self.send_response(
                                conn, 'Added %s to head of queue' % jobname)
                        job_runner.wake_runner_signal()
                    break
                elif data.startswith('SHOWJOB '):
                    jobname = data[8:]
                    self.send_response(conn,
                                       self._show_job(jobname, job_runner))
                    break
                elif data == 'STATUS':
                    ret = "Run-queue: \n  %s\n" % "\n  ".join(
                        [repr({
                            'name': x['name'], 'pid': x['pid'],
                            'started': time.strftime(
                                '%H:%M.%S', time.localtime(x['started'])),
                        })
                         for x in job_runner.job_queue.get_running_jobs()])

                    ret += 'Ready jobs: \n  %s\n' % "\n  ".join(
                        [str(x) for x in job_runner.job_queue.get_run_queue()])

                    ret += 'Threads: \n  %s' % "\n  ".join(
                        [str(x) for x in threading.enumerate()])

                    tmp = job_runner.job_queue.get_known_jobs().keys()
                    tmp.sort()
                    ret += '\n%-35s %s\n' % ('Known jobs',
                                             '  Last run  Last duration')
                    for k in tmp:
                        t2 = job_runner.job_queue._last_run[k]
                        human_part = ""
                        if t2:
                            human_part = " (%s)" % time.strftime(
                                "%F %T", time.localtime(t2))
                        logger.debug("Last run of '%s' is '%s'%s",
                                     k, t2, human_part)
                        if t2:
                            t = time.strftime('%H:%M.%S', time.localtime(t2))
                            days = int((time.time()-t2)/to_seconds(days=1))
                        else:
                            t = 'unknown '
                            days = 0
                        t2 = job_runner.job_queue._last_duration[k]
                        if t2:
                            t += '  ' + time.strftime('%H:%M.%S',
                                                      time.gmtime(t2))
                        else:
                            t += '  unknown'
                        if days:
                            t += " (%i days ago)" % days
                        ret += "  %-35s %s\n" % (k, t)
                    if job_runner.sleep_to:
                        ret += 'Sleep to %s (%i seconds)\n' % (
                            time.strftime('%H:%M.%S',
                                          time.localtime(job_runner.sleep_to)),
                            job_runner.sleep_to - time.time())
                    if job_runner.queue_paused_at:
                        ret += "Notice: Queue paused for %s hours\n" % (
                            time.strftime(
                                '%H:%M.%S',
                                time.gmtime(time.time() -
                                            job_runner.queue_paused_at)))
                    self.send_response(conn, ret)
                    break
                elif data == 'PING':
                    self.send_response(conn, 'PONG')
                    break
                else:
                    print "Unkown command: %s" % data
                if not data:
                    break
            conn.close()

    def ping_server(self):
        try:
            os.stat(cereconf.JOB_RUNNER_SOCKET)
            if self.send_cmd("PING") == 'PONG':
                return 1
        except socket.error:   # No server seems to be running
            print "WARNING: Removing stale socket"
            os.unlink(cereconf.JOB_RUNNER_SOCKET)
            pass
        except OSError:        # File didn't exist
            pass
        return 0

    def send_response(self, sock, msg):
        """Send response, including .\n response terminator"""
        if msg == ".\n":
            msg = "..\n"
        msg = msg.replace("\n.\n", "\n..\n")
        sock.send("%s\n.\n" % msg)

    def send_cmd(self, cmd, timeout=2):
        """
        Send command, decode and return response.
        Raises SocketHandling.Timeout if no response has come
        in timeout seconds.
        """
        signal.alarm(timeout)
        try:
            self.socket = socket.socket(socket.AF_UNIX)
            self.socket.connect(cereconf.JOB_RUNNER_SOCKET)
            self.socket.send("%s\n" % cmd)

            ret = ''
            while 1:
                tmp = self.socket.recv(1024)
                if not tmp:
                    break
                if tmp == ".\n" or tmp.find("\n.\n") != -1:
                    tmp = tmp.replace("\n..\n", "\n.\n")
                    ret += tmp[:-2]
                    break
                ret += tmp.replace("\n..\n", "\n.\n")
            ret = ret.strip()
            self.socket.close()
        except:
            signal.alarm(0)
            raise
        signal.alarm(0)
        return ret

    def cleanup(self):
        if not self._is_listening:
            return
        try:
            os.unlink(cereconf.JOB_RUNNER_SOCKET)
        except OSError:
            pass

    def __del__(self):
        self.cleanup()
