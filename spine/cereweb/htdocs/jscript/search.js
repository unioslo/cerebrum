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

// Used by httprequests to get the right url
webroot = "";  // Should be overriden by includer

// Runs when the page is finished loading.
YAHOO.util.Event.addListener(window, 'load', SR_init_listeners);

// Initialises the listener on the reset button.
function SR_init_listeners() {
    var clear_button = document.getElementById('search_clear');
    YAHOO.util.Event.addListener(clear_button, 'click', SR_clear);
}

// Clears the searchform.
function SR_clear() {
    var form = document.getElementById('search_form');
    
    //Resets all elements in the form.
    for(var i = 0; i < form.length; i++) {
        if (form.elements[i].type == "text") {
            form.elements[i].value = "";
        }
    }

    //Tells the server to clear the lastsearch.
    var url = webroot + "/entity/clear_search?url=";
    var req = get_http_requester();
    req.open("GET", url+form.action, true);
    req.onreadystatechange = get_http_response(req);
    req.send(null);
}

