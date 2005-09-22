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

// Where we came from, used to go back if wanted.
var referer_url = ""; // Should be overriden by includer 

addLoadEvent(Err_init_listeners);

function Err_init_listeners() {
    var traceback_link = document.getElementById('show_traceback');
    var retry_link = document.getElementById('retry');
    var back_link = document.getElementById('back');
    
    addEvent(traceback_link, 'click', Err_show_traceback);
    addEvent(retry_link, 'click', Err_retry);
    addEvent(back_link, 'click', Err_back);
}

// Show/Hide the traceback block.
function Err_show_traceback() {
    var link = document.getElementById('show_traceback');
    var traceback = document.getElementById('traceback');

    if (traceback.style.display != "block") {
        traceback.style.display = "block";
        set_link_text(link, "hide traceback")
    } else {
        traceback.style.display = "none";
        set_link_text(link, "show traceback")
    }
}

// Reloads the page from the server.
function Err_retry() {
    window.location.reload(true);
}

// Redirects the users to where he came from.
function Err_back() {
    window.location.href = referer_url;
}

