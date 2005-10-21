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
 * has timed out. This script will not work with other scrips wich also
 * uses window.setTimeout().
 *
 * Note: All times are in seconds.
 */

// Time from side refresh untill sessios times out.
var timeout = 600;  // Should be overriden by includer.

// Time left when warning should be given. Set to 0 to disable warning.
var TO_warning = 120;

// Runs when the page is finished loading.
addLoadEvent(TO_init);

// Initialize timeout when warning should be given.
function TO_init() {
    //NB: setTimeout expects miliseconds.

    if (TO_warning > 0) {
        window.setTimeout('TO_warn()', (timeout - TO_warning) * 1000);
    } else {
        window.setTimeout('TO_timedout()', timeout * 1000);
    }
}

// Warns the user that the session will timeout soon.
function TO_warn() {
    window.setTimeout('TO_timedout()', TO_warning);
    var time = TO_warning + " seconds";
    alert("Cereweb session warning:\nYour session will time out in "+time+".");
}

// Warns the user that the session has timed out.
function TO_timedout() {
    var warning_div = document.getElementById('session_warning');
    var msg = "Your session has timed out, you should relogin to get a new session.";
    warning_div.appendChild(document.createTextNode(msg));
    warning_div.style.display = "block";
}

