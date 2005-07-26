//
// Copyright 2004, 2005 University of Oslo, Norway
//
// This file is part of Cerebrum.
//
// Cerebrum is free software; you can redistribute it and/or modify it
// under the terms of the GNU General Public License as published by
// the Free Software Foundation; either version 2 of the License, or
// (at your option) any later version.
//
// Cerebrum is distributed in the hope that it will be useful, but
// WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
// General Public License for more details.
// 
// You should have received a copy of the GNU General Public License
// along with Cerebrum; if not, write to the Free Software Foundation,
// Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.


//var webroot = "";  // Should be set by includer

/* addLoadEvent by Simon Willisons blog on sitepoint.com */
function addLoadEvent(func) {
    var oldonload = window.onload;
    if (typeof window.onload != 'function') {
        window.onload = func;
    } else {
        window.onload = function() {
            oldonload();
            func();
        };
    }
}

/* addEvent by Peter-Paul Kochs blog on quirksmode.org */
function addEvent(obj, sType, fn){
    if (obj.addEventListener){
        obj.addEventListener(sType, fn, false);
    } else if (obj.attachEvent) {
        var r = obj.attachEvent('on'+sType, fn);
    } else {
        WL_error("EventHandler could not be attached.");
    }
}

// Cross-browser-compatible method for creating xmlhttp-objects.
function get_http_requester() {
    var requester = null;
    try {
        requester = new XMLHttpRequest();
    } catch (err) {
        try {
            requester = new ActiveXObject("Microsoft.XMLHTTP");
        } catch (err) {
            WL_error("Unable to create XMLHttpRequest-object.");
        }
    }
    return requester
}

// Calls func if set and the http respons was successfull.
function WL_check_http_response(req, func) {
    return function() {
        if (req.readyState == 4) {
            if (req.status != 200) {
                WL_error("HttpRequest "+req.status+":\n"+req.responseText);
            } else {
                if (func) {
                    func();
                }
            }
        }
    };
}

// Show errors to the user, in a inobtrusive way.
function WL_error(msg) {
    alert("WLerror:"+msg);
    
    var action_div = document.getElementById('WL_actions');
    var error_div = document.getElementById('WL_errors');
    var error_list = document.getElementById('WL_errorlist');

    msg = error_list.innerText + msg + '\n'; 

    action_div.style.display = "none";
    error_div.style.display = "block";
    error_list.innerText = msg;
}

// Registers listeners to worklist-buttons.
function WL_init_listeners() {
    var all_button = document.getElementById('WL_all');
    var none_button = document.getElementById('WL_none');
    var invert_button = document.getElementById('WL_invert');
    var forget_button = document.getElementById('WL_forget');
    var select_list = document.getElementById('WL_select');

    addEvent(all_button, 'click', WL_select_all);
    addEvent(none_button, 'click', WL_select_none);
    addEvent(invert_button, 'click', WL_invert);
    addEvent(forget_button, 'click', WL_forget);
    addEvent(select_list, 'change', WL_view_actions);
}

// Fill WL_worklist and change link-texts to forget.
function WL_init_elements() {
    var worklist = document.getElementById('WL_select');

    // fill WL_worklist with the info already in the select
    for (var i = 0; i < worklist.options.length; i++) {
        var opt_name = worklist.options[i].text;
        WL_worklist[i] = new Array(
            worklist.options[i].value,
            opt_name.split(":",1)[0],
            opt_name.slice(opt_name.split(":",1)[0].length+1)
        );
    }
    
    // change the text on links to forget for things already in the worklist
    for (var i = 0; i < worklist.length; i++) {
        var id = WL_worklist[i][0];
        var link = document.getElementById('WL_link_'+id);
        if (link) {
            link.innerText = "forget";
        }
    }
}

// WL_worklist : ((id, class, name), ...)
var WL_max_elements = 20;
var WL_worklist = new Array(WL_max_elements);
for (var i = 0; i < WL_max_elements; i++) {
    WL_worklist[i] = new Array(null, '', '');
}

// After the page is finished loading, add listeners and fill worklist.
addLoadEvent(WL_init_listeners);
addLoadEvent(WL_init_elements);

function WL_view_actions() {
}

// method to add an entity to the worklist
function WL_remember(id, cls, name) {
    var worklist = document.getElementById('WL_select');

    if (worklist.length >= WL_max_elements) {
        alert("Cannot add any more objects to the worklist.");
        return;
    }

    //element already remebered, remove
    for (var i = 0; i < WL_max_elements; i++) {
        if (WL_worklist[i][0] == id) {
            WL_forget_by_pos(i);
            
            // tell the server that we have removed some element.
            var req = get_http_requester();
            var remove_url = webroot + '/worklist/remove';
            req.open("GET", remove_url+"?id="+id, true);
            req.onreadystatechange = WL_check_http_response(req, null);
            req.send(null);
    
            return;
        }
    }

    //remove option -Remembered objects-
    if (worklist[0].text == "-Remembered objects-") {
        worklist.remove(0);
    }

    var new_elm = document.createElement('option');
    new_elm.text = name;
    new_elm.value = id;

    try {
        worklist.add(new_elm, null); // standards compliant; doesnt work in IE
    } catch(ex) {
        worklist.add(new_elm); // IE only
    }

    // add element to WL_worklist
    WL_worklist[worklist.length-1] = new Array(id, cls, name);

    // change the text on the element by id
    var link = document.getElementById('WL_link_'+id);
    link.innerText = "forget";

    // tell the server that we have added an element.
    var requester = get_http_requester();
    name = name.slice(name.split(":",1)[0].length+1)
    var add_url = webroot + '/worklist/add';
    requester.open("GET", add_url+"?id="+id+"&cls="+cls+"&name="+name, true);
    requester.onreadystatechange = WL_check_http_response(requester, null);
    requester.send(null);
}

// method for removing an element from the worklist by position
function WL_forget_by_pos(pos) {
    var worklist = document.getElementById('WL_select');
    if (pos >= 0) {
        // remove element from WL_worklist and worklist
        var id = WL_worklist[pos][0];
        WL_worklist[pos] = new Array(null, "", "");
        worklist.remove(pos);

        if (worklist.length == 0) {
            var option = document.createElement('option');
            option.text = "-Remembered objects-";
            worklist.add(option, 0);
        }

        // change the text on the element by id
        var link = document.getElementById('WL_link_'+id)
        if (link != null) {
            link.innerText = "remember";
        }
    }
}

// method for removing selected items from worklist
function WL_forget() {
    var worklist = document.getElementById('WL_select')
    var ids = new Array(WL_max_elements);
    var j = 0;
    for (var i = worklist.length-1; i >= 0; i--) {
        if (worklist[i].selected == 1) {
            if (worklist[i].text != "-Remembered objects-") {
                ids[j++] = worklist[i].value;
            }
            WL_forget_by_pos(i);
        }
    }
    
    // tell the server that we have removed some element.
    var requester = get_http_requester();
    var remove_url = webroot + '/worklist/remove';
    requester.open("GET", remove_url+"?ids="+ids, true);
    requester.onreadystatechange = WL_check_http_response(requester, null);
    requester.send(null);
}

function WL_select_all() {
    var worklist = document.getElementById('WL_select')
    for (var i = 0; i < worklist.length; i++) {
        worklist[i].selected = 1;
    }
}

function WL_select_none() {
    var worklist = document.getElementById('WL_select')
    for (var i = 0; i < worklist.length; i++) {
        worklist[i].selected = 0;
    }
}

function WL_invert() {
    var worklist = document.getElementById('WL_select')
    for (var i = 0; i < worklist.length; i++) {
        if (worklist[i].selected == 1) {
            worklist[i].selected = 0;
        } else {
            worklist[i].selected = 1;
        }
    }
}

