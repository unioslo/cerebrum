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

// Time in ms between each server request to update time left.
var TO_check_interval = 60 * 1000;

// Time in s before the session times out to warn the client.
var TO_warning_time = 120;

var TO_timerid = 0; // Contains the last id for the scheduled check.
var TO_has_warned = false; // To prevent us from warning the user twice.

function TO_init() {
    var warn_title = "Cereweb session warning";
    var warn_text  = "You session will time out in " + TO_warning_time +
        " seconds. Do you want to extend your session time?";
    YAHOO.cereweb.timeOutDialog =
        new YAHOO.widget.SimpleDialog('timeOutDialog',
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

function TO_allow_timeout() {
    YAHOO.cereweb.timeOutDialog.hide();
}

// Requests the server to keep the session alive for another periode.
function TO_keepalive() {
    YAHOO.cereweb.timeOutDialog.hide();
    TO_has_warned = false;
    stopTimer();

    var callback = {
        success: function(o) {
            if (o.responseText == "true") {
                startTimer('TO_check()', TO_check_interval)
            } else if (o.responseText == "false") {
                TO_timed_out(); // Couldnt keep alive since it already timed out.
            } else {
                YAHOO.log('Keepalive failed for unknown reasons.')
                TO_check();
            }
        },
        failure: function(o) {
            YAHOO.log('Timed out.');
        },
        timeout: 5000,
    }
    
    // Ask the server to keep the session alive.
    var connectionObject = YAHOO.util.Connect.asyncRequest('GET',
        '/session_keep_alive?hash=' + Math.random(), callback);
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

// Check time left until the session times out.
function TO_check() {
    stopTimer();
    
    var callback = {
        success: function (o) {
            var time_left = parseInt(o.responseText);
            YAHOO.log('Time left: ' + time_left);

            if (time_left < TO_warning_time) {
                startTimer('TO_timed_out()', time_left); 
                TO_warn();
            } else {
                startTimer('TO_check()', TO_check_interval);
            }
        },
        failure: function(o) {
            YAHOO.log("Couldn't connect to server.");
            startTimer('TO_check()', TO_check_interval)
        },
        timeout: 5000,
    }

    // NB: internet explorer and opera has a 'bug' where get-requests
    // are cached, we circumvent this by adding a random hash to the req.
    var connectionObject = YAHOO.util.Connect.asyncRequest('GET',
        '/session_time_left?hash=' + Math.random(), callback);
}

// Warns the user that the session will timeout soon.
function TO_warn() {
    if (!TO_has_warned) {
        TO_has_warned = true;
        YAHOO.cereweb.timeOutDialog.show();
    }
}

// Warns the user that the session has timed out.
function TO_timed_out() {
    stopTimer();
    YAHOO.cereweb.timeOutDialog.hide();
    var warning_div = document.getElementById('session_warning');
    var msg = "Your session has timed out, login to get a new session.";
    warning_div.appendChild(document.createTextNode(msg));
    warning_div.style.display = "block";
}

