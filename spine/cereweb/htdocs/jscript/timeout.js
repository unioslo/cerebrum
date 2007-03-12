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


var TO_check_interval = 60 * 1000; // ms
var TO_warning_time = 120; // sec
var TO_timeout = 5 * 1000; // ms before an AJAX call should time out.
var TO_timeout_fail = TO_timeout; // ms before retrying when ajax call fails.
var TO_timeout_fail_inc = 1.1; // Factor to increase retry time to prevent hammering.
var TO_timeout_fail_max = TO_check_interval; // Max wait between failed ajax calls.
var TO_timerid = 0; // Keep track of the timer so we can cancel it.

function TO_init() {
    var el = cereweb.createDiv('timeOutDialog');
    var warn_title = "Cereweb session warning";
    var warn_text  = "You session will time out in " + TO_warning_time +
        " seconds. Do you want to extend your session time?";
    YAHOO.cereweb.timeOutDialog =
        new YAHOO.widget.SimpleDialog(el,
            { 
                width: "500px",
                fixedcenter: true,
                visible: false,
                draggable: false,
                close: true,
                text: warn_text,
                icon: YAHOO.widget.SimpleDialog.ICON_HELP,
                constraintoviewport: true,
                buttons: [ { text:'Yes', handler:TO_keepalive, isDefault:true },
                           { text:'No', handler:TO_allow_timeout }]
        });
    YAHOO.cereweb.timeOutDialog.setHeader(warn_title);
    YAHOO.cereweb.timeOutDialog.render();
    startTimer('TO_check()', TO_check_interval)
}
YAHOO.util.Event.addListener(window, 'load', TO_init);

// Check time left until the session times out.
function TO_check() {
    stopTimer();
    
    var callback = {
        success: function (o) {
            TO_timeout_fail = TO_timeout; // Reset fail-timeout value.
            var time_left = parseInt(o.responseText);
            if (time_left < TO_warning_time) {
                startTimer('TO_time_out()', time_left); 
                YAHOO.cereweb.timeOutDialog.show();
            } else {
                TO_hide_warning();
                startTimer('TO_check()', TO_check_interval);
            }
        },
        failure: TO_connection_failure,
        timeout: TO_timeout
    }

    url = '/session_time_left'
    data = 'nocache=' + Math.random()
    var cObj = YAHOO.util.Connect.asyncRequest('POST', url, callback, data);
}

function TO_hide_warning() {
    var warning = YD.get('session_warning');
    if (warning)
        warning.style.display = "none";
}
// Requests the server to keep the session alive for another periode.
function TO_keepalive() {
    YAHOO.cereweb.timeOutDialog.hide();
    stopTimer();

    var callback = {
        success: function(o) {
            if (o.responseText == "true") {
                startTimer('TO_check()', TO_check_interval)
            } else if (o.responseText == "false") {
                TO_time_out(); // Couldnt keep alive since it already timed out.
            } else {
                YAHOO.log('Keepalive failed for unknown reasons.')
                TO_check();
            }
        },
        failure: TO_connection_failure,
        timeout: TO_timeout
    }
    
    url = '/session_keep_alive'
    data = 'nocache=' + Math.random()
    var cObj = YAHOO.util.Connect.asyncRequest('POST', url, callback, data);
}

function TO_allow_timeout() {
    YAHOO.cereweb.timeOutDialog.hide();
}

function startTimer(fun, time) {
    if (TO_timerid) {
        YAHOO.log('Attempted to start extra timer thread.');
        YAHOO.log(fun);
    } else {
        TO_timerid = window.setTimeout(fun, time);
    }
}

function stopTimer() {
    if (TO_timerid) {
        window.clearTimeout(TO_timerid);
        TO_timerid = 0;
    } else {
        YAHOO.log('Tried to stop nonexisting timer.');
    }
}

function TO_connection_failure(o) {
    startTimer('TO_check()', TO_timeout_fail);
    if (TO_timeout_fail < TO_timeout_fail_max)
        TO_timeout_fail = TO_timeout_fail * TO_timeout_fail_inc;

    var msg = "<p>It seems that the server is unavailable.  This message\
 will disappear as soon as the server is available again, so please be patient.\
 If nothing happens within five minutes, feel free to call (735) 91500 and\
 notify Orakeltjenesten of the situation.</p>";
    TO_show_warning(msg);
}

function TO_show_warning(msg) {
    var warning_div = YD.get('session_warning');
    if (!warning_div)
        warning_div = cereweb.createDiv('session_warning', 'messages');
    warning_div.innerHTML = msg;
    warning_div.style.display = "block";
}

// Warns the user that the session has timed out.
function TO_time_out() {
    stopTimer();
    YAHOO.cereweb.timeOutDialog.hide();

    var msg = 'Your session has timed out, <a href="/login?redirect=' +
               encodeURIComponent(location.href) +
              '">click here</a> to get a new session.';
    TO_show_warning(msg);
}

if(cerebug) {
    log('timeout is loaded');
}
