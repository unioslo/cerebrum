# -*- coding: iso-8859-1 -*-
import time
import socket
import signal
import os
import threading

import cereconf
from Cerebrum import Errors

class When(object):
    def __init__(self, freq=None, time=None):
        """Indicates that a job should be ran either with a specified
        frequency, or at the specified time"""
        assert freq is not None or time is not None
        assert not (freq is not None and time is not None)
        self.freq = freq
        self.time = time

    def next_delta(self, last_time, current_time):
        """Returns # seconds til the next time this job should run
        """
        if self.freq is not None:
            return last_time + self.freq - current_time
        else:
            times = []
            for t in self.time:
                d = t.next_time(last_time)
                times.append(d + last_time - current_time)
            return min(times)

    def __str__(self):
        if self.time:
            return "time=(%s)" % ",".join([str(t) for t in self.time])
        return "freq=%s" % time.strftime('%H:%M.%S',
                                         time.gmtime(self.freq))

class Time(object):
    def __init__(self, min=None, hour=None, wday=None):
        """Emulate time part of crontab(5), None=*"""
        self.min = min
        if min is not None:
            self.min.sort()
        self.hour = hour
        if hour is not None:
            self.hour.sort()
        self.wday = wday
        if wday is not None:
            self.wday.sort()

    def _next_list_value(self, val, list, size):
        for n in list:
            if n > val:
                return n, 0
        return min(list), 1

    def next_time(self, prev_time):
        """Return the number of seconds until next time after num"""
        hour, min, sec, wday = (time.localtime(prev_time))[3:7]

        add_week = 0
        for i in range(10):
            if self.wday is not None and wday not in self.wday:
                # finn midnatt neste ukedag
                hour = 0
                min = 0
                t, wrap = self._next_list_value(wday, self.wday, 6)
                wday = t
                if wrap:
                    add_week = 1

            if self.hour is not None and hour not in self.hour:
                # finn neste time, evt neste ukedag
                min = 0
                t, wrap = self._next_list_value(hour, self.hour, 23)
                hour = t
                if wrap:
                    wday += 1
                    continue

            if self.min is not None and min not in self.min:
                # finn neste minutt, evt neste ukedag
                t, wrap = self._next_list_value(min, self.min, 59)
                min = t
                if wrap:
                    hour += 1
                    continue

            # Now calculate the diff
            old_hour, old_min, old_sec, old_wday = (time.localtime(prev_time))[3:7]
            week_start_delta = (old_wday*24*3600 + old_hour*3600 + old_min*60 + old_sec)

            ret = add_week*7*24*3600 + wday*24*3600 + hour*3600 + min*60 - week_start_delta

            # Assert that the time we find is after the previous time
            if ret <= 0:
                if self.min is not None:
                    min += 1
                elif self.hour is not None:
                    hour += 1
                elif self.wday is not None:
                    wday += 1
                continue
            return ret
        raise ValueError, "Programming error for %i" % prev_time

    def __str__(self):
        ret = []
        if self.wday:
            ret.append("d="+":".join(["%i" % w for w in self.wday]))
        if self.hour:
            ret.append("h="+":".join(["%i" % w for w in self.hour]))
        if self.hour:
            ret.append("m="+":".join(["%i" % w for w in self.min]))
        return ",".join(ret)
    
class SocketHandling(object):
    """Simple class for handling client and server communication to
    job_runner"""

    Timeout = 'timeout'
    
    def timeout(sig, frame) :
        raise SocketHandling.Timeout
    timeout = staticmethod(timeout)

    def __init__(self):
        signal.signal(signal.SIGALRM, SocketHandling.timeout)

    def start_listener(self, job_runner):
        self.socket = socket.socket(socket.AF_UNIX)
        self.socket.bind(cereconf.JOB_RUNNER_SOCKET)
        self.socket.listen(1)
        while True:
            conn, addr = self.socket.accept()
            while 1:
                data = conn.recv(1024).strip()
                if data == 'RELOAD':
                    job_runner.reload_scheduled_jobs()
                    job_runner.wake_runner()
                    conn.send('OK\n')
                    break
                elif data == 'QUIT':
                    job_runner.ready_to_run = ('quit',)
                    job_runner.wake_runner()
                    conn.send('QUIT is now only entry in ready-to-run queue\n')
                    break
                elif data == 'STATUS':
                    ret = 'Run-queue: %s\nThreads: %s\nKnown jobs: %s\n' % (
                        job_runner.ready_to_run, threading.enumerate(),
                        job_runner.all_jobs.keys())
                    if job_runner.sleep_to is None:
                        ret += 'Status: running %s\n' % job_runner.current_job
                    else:
                        ret += 'Status: sleeping for %f seconds\n' % \
                               (job_runner.sleep_to - time.time())
                    conn.send(ret)
                    break
                elif data == 'PING':
                    conn.send('PONG\n')
                    break
                else:
                    print "Unkown command: %s" % data
                if not data: break
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

    def send_cmd(self, cmd, timeout=2):
        signal.alarm(timeout)
        try:
            self.socket = socket.socket(socket.AF_UNIX)
            self.socket.connect(cereconf.JOB_RUNNER_SOCKET)
            self.socket.send("%s\n" % cmd)
            ret = self.socket.recv(1024).strip()
            self.socket.close()
        except:
            signal.alarm(0)
            raise
        signal.alarm(0)
        return ret

    def __del__(self):
        try:
            os.unlink(cereconf.JOB_RUNNER_SOCKET)
        except OSError:
            pass

class DbQueueHandler(object):
    def __init__(self, db, logger):
        self.db = db
        self.logger = logger

    def get_last_run(self):
        ret = {}
        for r in self.db.query(
            """SELECT id, timestamp
            FROM [:table schema=cerebrum name=job_ran]"""):
            ret[r['id']] = r['timestamp'].ticks()
        self.logger.debug("get_last_run: %s" % ret)
        return ret

    def update_last_run(self, id, timestamp):
        timestamp = self.db.TimestampFromTicks(timestamp)
        self.logger.debug("update_last_run(%s, %s)" % (id, timestamp))

        try:
            self.db.query_1("""
            SELECT 'yes'
            FROM [:table schema=cerebrum name=job_ran]
            WHERE id=:id""", locals())
        except Errors.NotFoundError:
            self.db.execute("""
            INSERT INTO [:table schema=cerebrum name=job_ran]
            (id, timestamp)
            VALUES (:id, :timestamp)""", locals())
        else:
            self.db.execute("""UPDATE [:table schema=cerebrum name=job_ran]
            SET timestamp=:timestamp
            WHERE id=:id""", locals())
        self.db.commit()

    
