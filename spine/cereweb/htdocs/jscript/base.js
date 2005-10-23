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
var webroot = "";  // Should be overriden by includer

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
function get_http_response(req, func, errfunc) {
    return function() {
        if (req.readyState == 4) {
            if (req.status != 200) {
                if (errfunc) { 
                    errfunc("HttpRequest "+req.status+":\n"+req.responseText);
                }
            } else {
                if (func) {
                    func(req);
                }
            }
        }
    };
}

// Method which compares the elements of 2 arrays to see if they are equal.
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
function set_link_text(obj, text) {
    if (obj == null) {
        return;
    }
    
    obj.replaceChild(document.createTextNode(text), obj.firstChild);
}

