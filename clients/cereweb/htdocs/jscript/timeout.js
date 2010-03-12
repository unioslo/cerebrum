/*
 * Copyright 2004, 2005 University of Oslo, Norway
 *
 * This file is part of Cerebrum.
 *
 * Cerebrum is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * Cerebrum is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Cerebrum; if not, write to the Free Software Foundation,
 * Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
 */

/*
 * Warns the user that the session is about to time out and/or when it
 * has timed out. The warning given before it times out allows the user
 * to request the server to keep the session alive for another periode.
 *
 * The time calculation is done server-side, and this script just checks
 * in given intervals if its time to warn the user and/or if the session
 * has timed out.
 *
 * This script tries not to calculate the latency, which means in theory
 * there can be times where the script belives the session has timed out
 * when it hasnt, and vice versa.
 *
 * Note: All times are in seconds.
 */

cereweb.timeout = {
    init: function() {
        this.start_timer(this.config.interval)
    },
    config: {
        interval: 50 * 1000, // ms
        ajax_timeout: 5 * 1000, // ms before an AJAX call should time out.
        timeout_fail: 5 * 1000, // ms before retrying when ajax call fails.
        timeout_fail_inc: 1.1 // Factor to increase retry time to prevent hammering.
    },
    check: function() {
        // Check time left until the session times out.
        this.stop_timer();
        
        var callback = {
            success: function (o) {
                this._timeout_fail = this.config.timeout_fail; // Reset fail-timeout value.

                var session_active = o.responseText;
                if (session_active === "true") {
                    this.start_timer(this.config.interval);
                } else {
                    this.time_out(); 
                }
            },
            failure: function (o) {
                var timeout = this._timeout_fail || this.config.timeout_fail;
                this.start_timer(timeout);
                this._timeout_fail = timeout * this.config.timeout_fail_inc;

                var msg = "<p>It seems that the server is unavailable. " +
                          "Please check your network connection.  If you're " +
                          "certain that your network connection is ok, " +
                          "please try again in five minutes.  If the server " +
                          "remains unavailable, call (735) 91500 and notify " +
                          "Orakeltjenesten of the situation.</p>";
                
                cereweb.events.sessionError.fire('Connection failure');
                this.show_warning("Connection Failure", msg, true);
    },
            timeout: this.config.ajax_timeout,
            scope: this
        }

        var url = '/ajax/has_valid_session'
        var data = 'nocache=' + Math.random()
        var cObj = YAHOO.util.Connect.asyncRequest('POST', url, callback, data);
    },
    start_timer: function (time) {
        if (this.timer_id) {
            log('Attempted to start extra timer thread.');
            log(fun);
        } else {
            var self = this; // Fix scope.
            this.timer_id = window.setTimeout(function() { self.check(); }, time);
        }
    },
    stop_timer: function () {
        if (this.timer_id) {
            window.clearTimeout(this.timer_id);
            this.timer_id = false;
        } else {
            log('Tried to stop nonexisting timer.');
        }
    },
    show_warning: function (title, msg, is_error) {
        this.hide_warning();
        this.error_id = cereweb.msg.add(title, msg, is_error);
    },
    hide_warning: function () {
        if (this.error_id)
            cereweb.msg.remove(this.error_id);
    },
    time_out: function() {
        var msg = 'Your session has timed out, <a href="/login?redirect=' +
                  encodeURIComponent(location.href) +
                  '">click here</a> to get a new session.';

        cereweb.events.sessionError.fire('Session timed out');
        this.show_warning('Session Timed Out', msg, true);
    }
}
YAHOO.util.Event.addListener(window, 'load', cereweb.timeout.init, cereweb.timeout, true);


if(cereweb.debug) {
    log('timeout is loaded');
}
