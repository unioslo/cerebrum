#! /bin/sh
#
# skeleton	example file to build /etc/init.d/ scripts.
#		This file should be used to construct scripts for /etc/init.d.
#
#		Written by Miquel van Smoorenburg <miquels@cistron.nl>.
#		Modified for Debian 
#		by Ian Murdock <imurdock@gnu.ai.mit.edu>.
#
# Version:	@(#)skeleton  1.9  26-Feb-2001  miquels@cistron.nl
#
#DEBUG="debug"
#[ -n $DEBUG ] && set -x

PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
DAEMON_BOFHD=/usr/sbin/bofhd.py
DAEMON_JOB_R=/usr/sbin/job_runner.py
NAME=cerebrum
DESC=cerebrum
PID_BOFHD="$NAME-bofhd"
PID_JOB_R="$NAME-job_runner"
DAEMON_BOFHD_OPTS="--config-file /etc/cerebrum/config.dat"
DAEMON_JOB_R_OPTS=""
MANDATORY_FILES=( /etc/cerebrum/config.dat		 \
		  /etc/cerebrum/logging.ini		 \
		  /etc/cerebrum/cereconf.py		 \
#		  /etc/cerebrum/scheduled_jobs.py	 \
		  /etc/cerebrum/passwd-cerebrum@cerebrum \
		)

#[ -n $DEBUG ] && echo ${#MANDATORY_FILES[@]} ${MANDATORY_FILES[@]}
test -x $DAEMON_BOFHD || exit 0
test -x $DAEMON_JOB_R || exit 0


# Include cerebrum defaults if available
if [ -f /etc/default/cerebrum ] ; then
	. /etc/default/cerebrum
fi

set -e

check_mandatory_files_are_there() {
	local files_exist="true"
	for i in $(seq 0  $((${#MANDATORY_FILES[@]} - 1))) ; do
		if [ ! -f "${MANDATORY_FILES[$i]}" ] ; then
		echo "ERROR: The mandatory configuration file ${MANDATORY_FILES[$i]} is missing."
		return 1
		fi
	done
	return 0
}

case "$1" in
  start)
	if check_mandatory_files_are_there ; then
		echo -n "Starting $DESC: "
		start-stop-daemon --start --quiet --pidfile /var/run/$PID_BOFHD.pid \
			--chuid cerebrum --exec $DAEMON_BOFHD -- $DAEMON_BOFHD_OPTS
		start-stop-daemon --start --quiet --pidfile /var/run/$PID_JOB_R.pid \
			--chuid cerebrum --exec $DAEMON_JOB_R -- $DAEMON_JOB_R_OPTS
		echo "$NAME."
	fi
	;;
  stop)
	echo -n "Stopping $DESC: "
	start-stop-daemon --stop --quiet --pidfile /var/run/$PID_BOFHD.pid \
		--exec $DAEMON_BOFHD --oknodo
	start-stop-daemon --stop --quiet --pidfile /var/run/$PID_JOB_R.pid \
		--exec $DAEMON_JOB_R --oknodo
	echo "$NAME."
	;;
  reload|force-reload)
	echo "Reloading $DESC configuration files."
	start-stop-daemon --start --quiet --pidfile /var/run/$PID_JOB_R.pid \
		--chuid cerebrum --exec $DAEMON_JOB_R -- "--reload"
	;;
  restart)
	echo -n "Restarting $DESC: "
	start-stop-daemon --stop --quiet  --oknodo --pidfile \
		/var/run/$PID_BOFHD.pid --exec $DAEMON_BOFHD
	start-stop-daemon --stop --quiet  --oknodo --pidfile \
		/var/run/$PID_JOB_R.pid --exec $DAEMON_JOB_R
	sleep 1
	if check_mandatory_files_are_there ; then
		start-stop-daemon --start --quiet --pidfile /var/run/$PID_BOFHD.pid \
			--chuid cerebrum --exec $DAEMON_BOFHD -- $DAEMON_BOFHD_OPTS
		start-stop-daemon --start --quiet --pidfile /var/run/$PID_JOB_R.pid \
			--chuid cerebrum --exec $DAEMON_JOB_R -- $DAEMON_JOB_R_OPTS
	fi
	echo "$NAME."
	;;
  *)
	N=/etc/init.d/$NAME
	# echo "Usage: $N {start|stop|restart|reload|force-reload}" >&2
	echo "Usage: $N {start|stop|restart|force-reload}" >&2
	exit 1
	;;
esac

exit 0
