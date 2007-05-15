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
        this.start_timer(this.check, this.config.interval)
    },
    config: {
        interval: 50 * 1000, // ms
        warning_time: 120, // sec
        ajax_timeout: 5 * 1000, // ms before an AJAX call should time out.
        timeout_fail: 5 * 1000, // ms before retrying when ajax call fails.
        timeout_fail_inc: 1.1, // Factor to increase retry time to prevent hammering.
    },
    create_dialog: function() {
        var el = cereweb.createDiv('timeOutDialog');
        this.timeOutDialog =
            new YAHOO.widget.SimpleDialog(el,
                { 
                    width: "500px",
                    fixedcenter: true,
                    visible: false,
                    draggable: true,
                    close: true,
                    icon: YAHOO.widget.SimpleDialog.ICON_HELP,
                    constraintoviewport: true,
                    buttons: [ { text:'Yes', handler:this.keep_alive, isDefault:true },
                               { text:'No', handler:this.time_out }]
            });
        this.timeOutDialog.setHeader("Cereweb session warning");
        this.timeOutDialog.setBody("Your session will time out in " +
            this.config.warning_time +
            " seconds. Do you want to extend your session time?");
        this.timeOutDialog.render();
    },
    show_timeout_dialog: function() {
        if (!this.timeOutDialog)
            this.create_dialog();
        this.timeOutDialog.show();
    },
    check: function() {
        // Fix scope.
        if (this != cereweb.timeout){
            return cereweb.timeout.check();
        };

        // Check time left until the session times out.
        this.stop_timer();
        
        var callback = {
            success: function (o) {
                this.config.timeout_fail = this.config.ajax_timeout; // Reset fail-timeout value.
                var time_left = parseInt(o.responseText);
                if (time_left < this.config.warning_time) {
                    this.start_timer(this.time_out, time_left); 
                    this.show_timeout_dialog();
                } else {
                    this.hide_warning();
                    this.start_timer(this.check, this.config.interval);
                }
            },
            failure: this.connection_failure,
            timeout: this.config.ajax_timeout,
            scope: this
        }

        var url = '/session_time_left'
        var data = 'nocache=' + Math.random()
        var cObj = YAHOO.util.Connect.asyncRequest('POST', url, callback, data);
    },
    hide_warning: function () {
        var warning = YD.get('session_warning');
        if (warning)
            warning.style.display = "none";
    },
    keep_alive: function () {
        this.stop_timer();
        this.timeOutDialog.hide();

        var callback = {
            success: function(o) {
                if (o.responseText == "true") {
                    this.start_timer(this.check, this.config.interval);
                } else if (o.responseText == "false") {
                    this.time_out(); // Couldnt keep alive since it already timed out.
                } else {
                    log('cereweb.timeout.keep_alive failed for unknown reasons.')
                    this.check();
                }
            },
            failure: this.connection_failure,
            timeout: this.config.ajax_timeout,
            scope: this
        }
        
        var url = '/session_keep_alive'
        var data = 'nocache=' + Math.random()
        var cObj = YAHOO.util.Connect.asyncRequest('POST', url, callback, data);
    },
    start_timer: function (fun, time) {
        if (this.timer_id) {
            log('Attempted to start extra timer thread.');
            log(fun);
        } else {
            this.timer_id = window.setTimeout(fun, time);
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
    connection_failure: function (o) {
        this.start_timer(this.check, this.config.timeout_fail);
        this.config.timeout_fail = this.config.timeout_fail * this.config.timeout_fail_inc;

        var msg = "<p>It seems that the server is unavailable.  This message\
     will disappear as soon as the server is available again, so please be patient.\
     If nothing happens within five minutes, feel free to call (735) 91500 and\
     notify Orakeltjenesten of the situation.</p>";
        this.show_warning(msg);
    },
    show_warning: function (msg) {
        var warning_div = YD.get('session_warning');
        if (!warning_div)
            warning_div = cereweb.createDiv('session_warning', 'messages');
        warning_div.innerHTML = msg;
        warning_div.style.display = "block";
    },
    time_out: function() {
        // Fix scope.
        if (this != cereweb.timeout){
            return cereweb.timeout.time_out();
        };

        this.stop_timer();
        this.timeOutDialog.hide();

        var msg = 'Your session has timed out, <a href="/login?redirect=' +
                   encodeURIComponent(location.href) +
                  '">click here</a> to get a new session.';
        this.show_warning(msg);
    }
}
YAHOO.util.Event.addListener(window, 'load', cereweb.timeout.init, cereweb.timeout, true);


if(cereweb.debug) {
    log('timeout is loaded');
}
