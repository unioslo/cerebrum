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

        # TODO: support not-run interval to prevent running jobs when
        # FS is down etc.
        
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
    def __init__(self, min=None, hour=None, wday=None, max_freq=None):
        """Emulate time part of crontab(5), None=*

        When using Action.max_freq of X hours and a Time object for a
        specific time each day, the Action.max_freq setting may delay
        a job so that a job that should be ran at night is ran during
        daytime (provided that something has made the job ran at an
        unusual hour earlier).

        To avoid this, set Time.max_freq.  This prevents next_time
        from checking wheter the job should have started until
        last_time+max_freq has passed.  I.e. if max_freq=1 hour the
        job is set to run at 12:30, but was ran at 12:00, the job will
        not run until the next matching time after 13:00.  If the
        Action.max_freq had been used, the job would have ran at
        13:00."""

        # TBD: what mechanisms should be provided to prevent new jobs
        # from being ran immeadeately when the time is not currently
        # within the correct range?

        self.min = min
        if min is not None:
            self.min.sort()
        self.hour = hour
        if hour is not None:
            self.hour.sort()
        self.wday = wday
        if wday is not None:
            self.wday.sort()
        self.max_freq = max_freq or 0

    def _next_list_value(self, val, list, size):
        for n in list:
            if n > val:
                return n, 0
        return min(list), 1

    def next_time(self, prev_time):
        """Return the number of seconds until next time after num"""
        hour, min, sec, wday = (time.localtime(prev_time+self.max_freq))[3:7]

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
                elif data == 'STATUS':
                    ret = "Run-queue: \n  %s\n" % "\n  ".join(
                        [str({'name': x['name'], 'pid': x['pid'],
                              'started': time.strftime(
                        '%H:%M.%S', time.localtime(x['started']))})
                         for x in job_runner.job_queue.get_running_jobs()])

                    
                    ret += 'Ready jobs: \n  %s\n' % "\n  ".join(
                        [str(x) for x in job_runner.job_queue.get_run_queue()])
                    ret += 'Threads: \n  %s' % "\n  ".join(
                        [str(x) for x in threading.enumerate()])
                    tmp = job_runner.job_queue.get_known_jobs().keys()
                    tmp.sort()
                    ret += '\n%-35s %s\n' % ('Known jobs', '  Last run  Last duration')
                    for k in tmp:
                        t2 = job_runner.job_queue._last_run[k]
                        if t2:
                            t = time.strftime('%H:%M.%S', time.localtime(t2))
                            days = int((time.time()-t2)/(3600*24))
                        else:
                            t = 'unknown '
                            days = 0
                        t2 = job_runner.job_queue._last_duration[k]
                        if t2:
                            t += '  '+time.strftime('%H:%M.%S', time.gmtime(t2))
                        else:
                            t += '  unknown'
                        if days:
                            t += " (%i days ago)" % days
                        ret += "  %-35s %s\n" % (k, t)
                    if job_runner.sleep_to:
                        ret += 'Sleep to %s (%i seconds)\n' % (
                            time.strftime('%H:%M.%S', time.localtime(job_runner.sleep_to)),
                            job_runner.sleep_to - time.time())
                    self.send_response(conn, ret)
                    break
                elif data == 'PING':
                    self.send_response(conn, 'PONG')
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

    def send_response(self, sock, msg):
        """Send response, including .\n response terminator"""
        if msg == ".\n":
            msg = "..\n"
        msg = msg.replace("\n.\n", "\n..\n")
        sock.send("%s\n.\n" % msg)

    def send_cmd(self, cmd, timeout=2):
        """Send command, decode and return response"""
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

    
class JobQueue(object):
    """Handles the job-queuing in job_runner.

    Supports detecion of jobs that are independent of other jobs in
    the ready-to-run queue.  A job is independent if no pre/post jobs
    for the job exists in the queue.  This check is done recursively.
    Note that the order of pre/post entries for job does not indicate
    a dependency.
    """

    def __init__(self, scheduled_jobs, db, logger, debug_time=0):
        """Initialize the JobQueue.
        - scheduled_jobs is a reference to the module implementing
          get_jobs()
        - debug_time is number of seconds to increase current-time
          with for each call to get_next_job_time().  Default is to
          use the system-clock"""
        self._scheduled_jobs = scheduled_jobs 
        self.logger = logger
        self._known_jobs = {}
        self._run_queue = []
        self._running_jobs = []
        self._last_run = {}
        self._started_at = {}
        self._last_duration = {}         # For statistics in --status
        self.db_qh = DbQueueHandler(db, logger)
        self._debug_time=debug_time
        self.reload_scheduled_jobs()
        
    def reload_scheduled_jobs(self):
        reload(self._scheduled_jobs)
        for job_name, job_action in self._scheduled_jobs.get_jobs().items():
            self._add_known_job(job_name, job_action)
        # Also check if last_run values has been changed in the DB (we
        # don't bother with locking the update to the dict)
        for k, v in self.db_qh.get_last_run().items():
            self._last_run[k] = v

    def get_known_job(self, job_name):
        return self._known_jobs[job_name]
    
    def get_known_jobs(self):
        return self._known_jobs
    
    def _add_known_job(self, job_name, job_action):
        """Adds job to list of known jobs, preserving
        state-information if we already know about the job"""
        if job_action.call:
            job_action.call.set_logger(self.logger)
            job_action.call.set_id(job_name)
        if self._known_jobs.has_key(job_name):  # Preserve info when reloading
            job_action.copy_runtime_params(self._known_jobs[job_name])
        self._known_jobs[job_name] = job_action
        # By setting _last_run to the current time we prevent jobs
        # with a time-based When from being ran imeadeately (note that
        # reload_scheduled_jobs will overwrite this value if an entry
        # exists in the db)
        if job_action.when and job_action.when.time:
            self._last_run[job_name] = time.time()
        else:
            self._last_run[job_name] = 0
        self._last_duration[job_name] = 0

    def has_queued_prerequisite(self, job_name, depth=0):
        """Recursively check if job_name has a pre-requisite in run_queue."""

        # TBD: if a multi_ok=1 job has pre/post dependencies, it could
        # be delayed so that the same job is executed several times,
        # example (conver_ypmap is a post-job for both generate jobs):
        # ['generate_group', 'convert_ypmap', 'generate_passwd', 'convert_ypmap']
        # Is this a problem.  If so, how do we handle it?

        #self.logger.debug2("%shas_queued_prerequisite %s (%s) %s" % (
        #    "  " * depth, job_name, self._run_queue, self._running_jobs))

        # If a pre or post job of the main job is in the queue
        if depth > 0 and job_name in self._run_queue:
            return True
        # Job is currently running
        if job_name in [x[0] for x in self._running_jobs]:
            return True
        # Check any pre jobs for queue existence
        for tmp_name in self._known_jobs[job_name].pre:
            if self.has_queued_prerequisite(tmp_name, depth+1):
                return True
        # Check any post-jobs (except at depth=0, where the post-jobs
        # should be executed after us)
        if depth > 0:
            for tmp_name in self._known_jobs[job_name].post:
                if self.has_queued_prerequisite(tmp_name, depth+1):
                    return True
        else:
            # Check if any jobs in the queue has the main-job as a post-job.
            for tmp_name in self._run_queue:
                if job_name in self._known_jobs[tmp_name].post:
                    return True
            # any running jobs which has main-job as post-job
            for tmp_name in [x[0] for x in self._running_jobs]:
                if job_name in self._known_jobs[tmp_name].post:
                    return True
        return False

    def get_running_jobs(self):
        return [ {'name': x[0],
                  'pid': x[1],
                  'call': self._known_jobs[x[0]].call,
                  'started': self._started_at[x[0]]} for x in self._running_jobs ]

    def job_started(self, job_name, pid):
        self._running_jobs.append((job_name, pid))
        self._started_at[job_name] = time.time()
        self._run_queue.remove(job_name)
        self.logger.debug("Started [%s]" % job_name)

    def job_done(self, job_name, pid):
        if pid is not None:
            self._running_jobs.remove((job_name, pid))
        self._last_run[job_name] = time.time()

        if self._started_at.has_key(job_name):
            self.logger.debug("Completed [%s/%i] after %f seconds" % (
                job_name,  pid or -1, self._last_duration[job_name]))
            self._last_duration[job_name] = (
                self._last_run[job_name] - self._started_at[job_name])
        else:
            self._run_queue.remove(job_name)
            self.logger.debug("Completed [%s/%i] (start not set)" % (
                job_name,  pid or -1))
        self.db_qh.update_last_run(job_name, self._last_run[job_name])

    def get_run_queue(self):
        return self._run_queue
        
    def get_next_job_time(self, append=False):
        """find job that should be ran due to the current time, or
        being a pre-requisit of a ready job.  Returns number of
        seconds to next event, and stores the queue internaly."""

        global current_time
        jobs = self._known_jobs
        if append:
            queue = self._run_queue[:]
        else:
            queue = []
        if self._debug_time:
            current_time += self._debug_time
        else:
            current_time = time.time()
        min_delta = 999999
        for job_name in jobs.keys():
            delta = current_time - self._last_run[job_name]
            if jobs[job_name].when is not None:
                if append and job_name in self._run_queue:
                    # Without this, a previously added job that has a
                    # pre/post job with multi_ok=True would get the
                    # pre/post job appended once each time
                    # get_next_job_time was called.
                    continue

                # TODO: vent med å legge inn jobbene, slik at de som
                # har when=time kommer før de som har when=freq.                
                n = jobs[job_name].when.next_delta(
                    self._last_run[job_name], current_time)
                if n <= 0:
                    pre_len = len(queue)
                    self.insert_job(queue, job_name)
                    if pre_len == len(queue):
                        continue     # no jobs was added
                min_delta = min(n, min_delta)
        self.logger.debug("Delta=%i, a=%i/%i Queue: %s" % (
            min_delta, append, len(self._run_queue), str(queue)))
        self._run_queue = queue
        return min_delta

    def insert_job(self, queue, job_name):
        """Recursively add jobb and all its prerequisited jobs.

        We allways process all parents jobs, but they are only added to
        the queue if it won't violate max_freq."""
     
        this_job = self._known_jobs[job_name]
        for j in this_job.pre or []:
            self.insert_job(queue, j)

        if job_name not in queue or this_job.multi_ok:
            if (this_job.max_freq is None or
                current_time - self._last_run[job_name] > this_job.max_freq):
                if job_name not in [x[0] for x in self._running_jobs]:
                    # Don't add to queue if job is currently running
                    queue.append(job_name)

        for j in this_job.post or []:
            self.insert_job(queue, j)

    def dump_jobs(scheduled_jobs, details=0):
        jobs = scheduled_jobs.get_jobs()
        shown = {}

        def dump(name, indent):
            info = []
            if details > 0:
                if jobs[name].when:
                    info.append(str(jobs[name].when))
            if details > 1:
                if jobs[name].max_freq:
                    info.append("max_freq=%s" % time.strftime('%H:%M.%S',
                                                 time.gmtime(jobs[name].max_freq)))
            if details > 2:
                if jobs[name].pre:
                    info.append("pre="+str(jobs[name].pre))
                if jobs[name].post:
                    info.append("post="+str(jobs[name].post))
            print "%-40s %s" % ("   " * indent + name, ", ".join(info))
            shown[name] = True
            for k in jobs[name].pre or ():
                dump(k, indent + 2)
            for k in jobs[name].post or ():
                dump(k, indent + 2)

        for k, v in jobs.items():
            if v.when is None:
                continue
            dump(k, 0)
        print "Never run: \n%s" % "\n".join(
            ["  %s" % k for k in jobs.keys() if not shown.has_key(k)])

    dump_jobs = staticmethod(dump_jobs)

def run_tests():
    def parse_time(t):
        return time.mktime(time.strptime(t, '%Y-%m-%d %H:%M')) + time.timezone
    def format_time(sec):
        # %w has a different definition of day 0 than the localtime
        # tuple :-(
        return time.strftime('%Y-%m-%d %H:%M', time.localtime(sec)) + \
               " w=%i" % (time.localtime(sec))[6]
    def format_duration(sec):
        return "%s %id" % (
            time.strftime('%H:%M', time.gmtime(abs(delta))), int(delta/(3600*24)))
    tests = [(When(time=[Time(wday=[5], hour=[5], min=[30])]),
              (('2004-06-10 17:00', '2004-06-14 20:00'),
               ('2004-06-11 17:00', '2004-06-14 20:00'),
               ('2004-06-12 17:00', '2004-06-14 20:00'),
              )),
             (When(time=[Time(wday=[5], hour=[5], min=[30], max_freq=24*60*60)]),
              (('2004-06-10 17:00', '2004-06-14 20:00'),
               ('2004-06-11 17:00', '2004-06-14 20:00'),
               ('2004-06-12 17:00', '2004-06-14 20:00'),
              )),
             (When(time=[Time(hour=[4], min=[5])]),
              (('2004-06-01 03:00', '2004-06-01 04:00'),
               ('2004-06-01 03:00', '2004-06-01 04:10'),
               ('2004-06-01 03:00', '2004-06-01 04:20'),
              ))]
    for when, times in tests:
        print "When obj: ", when
        for t in times:
            # convert times to seconds since epoch in localtime
            prev = parse_time(t[0])
            now = parse_time(t[1])
            delta = when.next_delta(prev, now)
            print "  prev=%s, now=%s -> %s [delta=%i/%s]" % (
                format_time(prev), format_time(now), 
                format_time(now+delta), delta, format_duration(delta))

if __name__ == '__main__':
    run_tests()
