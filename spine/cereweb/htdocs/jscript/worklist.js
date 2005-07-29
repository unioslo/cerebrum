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

/* SETTINGS */

// Used by httprequests to get the right url
var webroot = "";  // Should be overriden by includer

// Max elements in the worklist.
var WL_max_elements = 20;

// WL_worklist : ((id, class, name), ...)
var WL_worklist = new Array();

// WL_actions : (((ids), action_name, action) ...)
var WL_actions = new Array();

// After the page is finished loading, run these methods.
addLoadEvent(WL_init_listeners);
addLoadEvent(WL_init_elements);
addLoadEvent(WL_init_actions);

/* END SETTINGS */

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

// Calls func if func is set and the http respons was successfull.
function get_http_response(req, func) {
    return function() {
        if (req.readyState == 4) {
            if (req.status != 200) {
                WL_error("HttpRequest "+req.status+":\n"+req.responseText);
            } else {
                if (func) {
                    func(req);
                }
            }
        }
    };
}

// method which compares the elements of 2 arrays to see if they are equal.
function compareArrays(arr1, arr2) {
    if (arr1.length != arr2.length) {
        return false;
    }
    
    var found = 0;
    for (var i = 0; i < arr1.length; i++) {
        for (var j = 0; j < arr2.length; j++) {
            if (arr1[i] == arr2[j]) {
                found++;
                break;
            }
        }
    }
    
    if (found == arr1.length) {
        return true;
    } else {
        return false;
    }
}

// Cross-browser method to set text on a Anchor DOM-object.
function WL_set_link_text(obj, text) {
    if (obj == null || obj.innerHTML == null) {
        return;
    }
    
    obj.replaceChild(document.createTextNode(text), obj.firstChild);
}

// Show errors to the user, in a inobtrusive way.
function WL_error(msg) {
    var action_div = document.getElementById('WL_actions');
    var error_div = document.getElementById('WL_errors');

    // hide all actions
    var actions = document.getElementById('WL_actions');
    for (var i = 0; i < actions.childNodes.length; i++) {
        if (actions.childNodes[i].style) {
            actions.childNodes[i].style.display = "none";
        }
    }

    error_div.appendChild(document.createTextNode(msg));
    error_div.style.display = "block";
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
        WL_set_link_text(link, "forget");
    }
}

// Load already created actions into the WL_actions-variable
function WL_init_actions() {
    // Fill WL_actions with the elements in WL_actions.
    var actions = document.getElementById('WL_actions');
    //TODO: for-løkke ++ dilldall

    // Call WL_view_actions() if any is selected.
    var worklist = document.getElementById('WL_select');
    for (var i = j = 0; i < worklist.length; i++) {
        if (worklist[i].selected == 1) {
            WL_view_actions(true);
            break;
        }
    }
}

// method which shows the actions for the select objects.
// method is executed when the user selects an element in the worklist.
function WL_view_actions(update_only) {
    // find which elements are selected.
    var worklist = document.getElementById('WL_select');
    var selected = new Array();
    var j = 0;
    for (var i = 0; i < worklist.length; i++) {
        if (worklist[i].selected == 1) {
            if (worklist[i].text != "-Remembered objects-") {
                selected[j++] = WL_worklist[i];
            }
        }
    }
  
    // hide all actions in.
    var actions = document.getElementById('WL_actions');
    for (var i = 0; i < actions.childNodes.length; i++) {
        if (actions.childNodes[i].style) {
            actions.childNodes[i].style.display = "none";
        }
    }
  
    // create and show the action for the selected items.
    if (selected[0] != null) {
        var action = WL_get_action(selected, update_only);
        actions.appendChild(action);
    } else {
        var action = document.getElementById('WL_action_info');
    }
    action.style.display = "block";
}

// Returns an action for the array with selected items.
function WL_get_action(selected, update_only) {
    // Check if the action for the selected items already exists.
    var action = null;
    var sortFunc = function(a, b) { return a - b; };
    var ids = Array(); // all ids of the selected options.
    for (var i = 0; i < selected.length; i++) {
        ids[i] = selected[i][0];
    }
    ids.sort(sortFunc);
    
    for (var i = 0; i < WL_actions.length; i++) {
        if (compareArrays(WL_actions[i][0],ids)) {
            action = WL_actions[i][2];
            break;
        }
    }

    var args = "?ids=" + ids;
    var update_url = webroot + '/worklist/selected';
    
    if (action == null) {
        action = WL_create_action(selected, ids);
        // TODO: add action.html to args.
    }
    
    if (update_only == null || update_only != true) {
        var req = get_http_requester();
        req.open("GET", update_url + args, true);
        req.onreadystatechange = get_http_response(req);
        req.send(null);
    }
    return action;
}

// Creates an action for the array with selected items.
function WL_create_action(selected, ids) {
    if (selected.length > 1) {
        // Do something clever here
    }
    
    var cls = selected[0][1];
    var action = document.getElementById('WL_action_'+cls.toLowerCase());
    var id = WL_actions.length < 1 ? 0 : WL_actions[WL_actions.length-1][1]+1;

    if (action == null) {
        action = document.getElementById('WL_action_default');
    }

    action = action.cloneNode(true);
    action.id = "WL_action_"+id;
    action.name = ids.toString();

    // replace the variables in the actionbox.
    //FIXME: doesnt work in firefox, since the urls in innerHTML is encoded.
    regex_id = /\{\{id\}\}/g;
    regex_class = /\{\{class\}\}/g;
    regex_name = /\{\{name\}\}/g;
    action.innerHTML = action.innerHTML.replace(regex_id, selected[0][0]);
    action.innerHTML = action.innerHTML.replace(regex_class, cls);
    action.innerHTML = action.innerHTML.replace(regex_name, selected[0][2]);
    
    // add the new action to WL_actions
    WL_actions[WL_actions.length] = new Array(ids, id, action);
    return action;
}

// method to add an entity to the worklist.
function WL_remember(id, cls, name) {
    var worklist = document.getElementById('WL_select');

    // element already remebered, remove.
    for (var i = 0; i < WL_worklist.length; i++) {
        if (WL_worklist[i][0] == id) {
            WL_forget_by_pos(i);
            
            // tell the server that we have removed some element.
            var req = get_http_requester();
            var remove_url = webroot + '/worklist/remove';
            req.open("GET", remove_url+"?id="+id, true);
            req.onreadystatechange = get_http_response(req);
            req.send(null);
    
            return;
        }
    }

    if (worklist.length >= WL_max_elements) {
        alert("Cannot add any more objects to the worklist.");
        return;
    }

    //remove option -Remembered objects-
    if (worklist[0].text == "-Remembered objects-") {
        worklist.remove(0);
    }

    var new_elm = document.createElement('option');
    new_elm.text = cls + ': ' + name;
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
    WL_set_link_text(link, "forget");

    // tell the server that we have added an element.
    var requester = get_http_requester();
    var add_url = webroot + '/worklist/add';
    requester.open("GET", add_url+"?id="+id+"&cls="+cls+"&name="+name, true);
    requester.onreadystatechange = get_http_response(requester);
    requester.send(null);
}

// method for removing an element from the worklist by position
function WL_forget_by_pos(pos) {
    var worklist = document.getElementById('WL_select');
    if (pos >= 0 && worklist[pos].text != "-Remembered objects-") {
        // remove element from WL_worklist and worklist
        var id = WL_worklist[pos][0];
        var end_slice = WL_worklist.slice(pos+1, WL_worklist.length);
        WL_worklist = WL_worklist.slice(0, pos).concat(end_slice);
        worklist.remove(pos);

        if (worklist.length == 0) {
            var option = document.createElement('option');
            option.text = "-Remembered objects-";
            worklist[0] = option;
        }

        // change the text on the element by id
        var link = document.getElementById('WL_link_'+id)
        WL_set_link_text(link, "remember");
    }
}

// method for removing selected items from worklist
function WL_forget() {
    var worklist = document.getElementById('WL_select')
    var ids = new Array();
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
    requester.onreadystatechange = get_http_response(requester);
    requester.send(null);
}

function WL_select_all() {
    var worklist = document.getElementById('WL_select')
    for (var i = 0; i < worklist.length; i++) {
        worklist[i].selected = 1;
    }
    
    WL_view_actions();
}

function WL_select_none() {
    var worklist = document.getElementById('WL_select')
    for (var i = 0; i < worklist.length; i++) {
        worklist[i].selected = 0;
    }
    
    WL_view_actions();
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
    
    WL_view_actions();
}


