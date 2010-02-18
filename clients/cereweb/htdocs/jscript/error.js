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

// No external dependencies.

// Show/Hide the error report form.
function Err_show_report() {
    var report = document.getElementById('report_div');

    if (report.style.display != "block") {
        report.style.display = "block";
    } else {
        report.style.display = "none";
    }
}

// Show/Hide the traceback block.
function Err_show_traceback() {
    var link = document.getElementById('show_traceback');
    var traceback = document.getElementById('traceback_div');

    if (traceback.style.display != "block") {
        traceback.style.display = "block";
        link.firstChild.data = "hide traceback";
    } else {
        traceback.style.display = "none";
        link.firstChild.data = "show traceback";
    }
}

// Reloads the page from the server.
function Err_retry() {
    window.location.reload(true);
}

// Redirects the users to where he came from.
// Cleaner to use referer, but with mod_python its not so easy to get?
function Err_back() {
    history.go(-1);
}
