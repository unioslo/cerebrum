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

// Time between each server request to update time left.
var TO_check_interval = 60;

// Time before the session times out to warn the client.
var TO_warning_time = 120;

var TO_timerid = null; // Contains the last id for the scheduled check.
var TO_has_warned = false; // To prevent us from warning the user twice.

// Runs when the page is finished loading.
addLoadEvent(TO_schedule);

// Schedule next timeout-check. 'time' in seconds.
function TO_schedule(time) {
    time = (time == null) ? TO_check_interval : time
    //NB: setTimeout expects miliseconds.
    TO_timerid = window.setTimeout('TO_check()', time * 1000);
}

// Check time left untill the session times out.
function TO_check() {
    // Ask the server for time left untill session timeout.
    // NB: internet explorer and opera has a 'bug' where get-requests
    // are cached, we circumvent this by adding a random hash to the req.
    var req = get_http_requester();
    req.open('GET', '/session_time_left?hash=' + Math.random(), true);
    req.onreadystatechange = get_http_response(req, TO_check_response);
    req.send(null);

    TO_schedule(); // Schedule another check.
}

// Handle the server check response.
function TO_check_response(req) {
    var latency = 3; // adjusting for latency
    var time_left = parseInt(req.responseText) - latency;

    // Enought time left.
    if (time_left > TO_warning_time + TO_check_interval + latency) { return; }

    // Time to warn the user.
    if (time_left > TO_warning_time && !TO_has_warned) {
        var warn_time = time_left - TO_warning_time;
        window.clearTimeout(TO_timerid);
         
        if (warn_time > 15) { TO_schedule(warn_time - 15); }
        else { TO_timerid = window.setTimeout('TO_warn()', warn_time); }
        return;
    }

    // Session times out soon.
    window.clearTimeout(TO_timerid);
    if (time_left > 10) { TO_schedule(time_left - 10); }
    else if (time_left <= 0) { TO_timed_out(); }
    else { TO_timerid = window.setTimeout('TO_timed_out()', time_left); }
}

// Warns the user that the session will timeout soon.
function TO_warn() {
    var time = TO_warning_time;
    var text = "Cereweb session warning:\nYour session will time out in ";
    text = text + time + " secconds.\nPress ok to extend your session time.";
    
    TO_has_warned = true;
    
    if (confirm(text)) { TO_keepalive(); }
    else { TO_check(); }
}

// Requests the server to keep the session alive for another periode.
function TO_keepalive() {
    var req = get_http_requester();
    var response = function(req) {
        if (req.responseText == "true") {
            TO_has_warned = false;
            TO_schedule(); // Schedule new checks for session timeout.
        } else if (req.responseText == "false") {
            TO_timed_out(); // Couldnt keep alive since it already timed out.
        } else {
            TO_check(); // Keepalive failed for unknown reasons.
        }
    };
    
    // Ask the server to keep the session alive.
    req.open('GET', '/session_keep_alive?hash=' + Math.random(), true);
    req.onreadystatechange = get_http_response(req, response);
    req.send(null);
}

// Warns the user that the session has timed out.
function TO_timed_out() {
    var warning_div = document.getElementById('session_warning');
    var msg = "Your session has timed out, login to get a new session.";
    warning_div.appendChild(document.createTextNode(msg));
    warning_div.style.display = "block";
}

