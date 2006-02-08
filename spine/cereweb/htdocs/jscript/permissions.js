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

var perm_methods = new Array(); // [{'cls', {'method', 'id', 'cur', 'rem'}},]
var perm_classes = new Array(); // [{'cls', Dom obj},]

addLoadEvent(Perm_init_listeners);
addLoadEvent(Perm_init_methods);

// Initialize listeners.
function Perm_init_listeners() {
    var all = document.getElementById('perm_all');
    var add = document.getElementById('perm_add');
    var rem = document.getElementById('perm_rem');
    var objs = document.getElementById('perm_objects');
    var mets = document.getElementById('perm_methods');
    var curr = document.getElementById('perm_current');

    addEvent(all, 'click', Perm_methods_all);
    addEvent(add, 'click', Perm_add);
    addEvent(rem, 'click', Perm_rem);
    addEvent(objs, 'change', Perm_objects_change);
    addEvent(mets, 'change', Perm_methods_change);
    addEvent(curr, 'change', Perm_current_change);
}

// Get all operations methods from server.
function Perm_init_methods() {
    var req = get_http_requester();
    req.open('GET', '/permissions/get_all_operations', true);
    req.onreadystatechange = get_http_response(req, Perm_methods_load);
    req.send(null);
}

// Handle response from the server.
function Perm_methods_load(req) {
    var objects = document.getElementById('perm_objects');
    var current = document.getElementById('perm_current');
    var methods = document.getElementById('perm_methods');
    var data = eval('(' + req.responseText + ')');
    perm_methods = data.methods;

    // Update perm_methods with current methods.
    for (i = 0; i < current.length; i++) {
        str = current[i].value.split(".");
        met = Perm_find_method(str[0], str[1]);
        if (met) { met.cur = true; }
    }

    // Fill object-list.
    objects.remove(0);
    for (i = 0; i < data.classes.length; i++)
        Perm_add_option(objects, data.classes[i]);

    // Fill method-list.
    methods.remove(0);
    Perm_objects_change();
}

// Find method in perm_methods by cls and name.
function Perm_find_method(cls, name) {
    for (k = 0; k < perm_methods.length; k++) {
        if (perm_methods[k].cls == cls) {
            for (l = 0; l < perm_methods[k].methods.length; l++) {
                if (perm_methods[k].methods[l].name == name)
                    return perm_methods[k].methods[l];
            }
            break;
        }
    }
    return null;
}

// Keeps the text on the all link accurate when the methodlist is changed.
function Perm_methods_change() {
    var all = document.getElementById('perm_all');
    var methods = document.getElementById('perm_methods');
    var all_selected = true;
    for (i = 0; i < methods.length; i++) {
        if (!methods[i].selected) {
            all_selected = false;
            break;
        }
    }
    set_link_text(all, all_selected ? 'none' : 'all')
}

// Selects all elements in method-list, or none if all are selected.
function Perm_methods_all() {
    var all = document.getElementById('perm_all');
    var methods = document.getElementById('perm_methods');
    var all_selected = true;
    for (i = 0; i < methods.length; i++) {
        if (!methods[i].selected) {
            all_selected = false;
            break;
        }
    }
    
    set_link_text(all, all_selected ? 'all' : 'none')
    
    if (all_selected) {
        for (i = 0; i < methods.length; i++)
            methods[i].selected = false;
    } else {
        for (i = 0; i < methods.length; i++)
            methods[i].selected = true;
    }
}

// Update methods when object-list is changed.
function Perm_objects_change() {
    var objects = document.getElementById('perm_objects');
    var methods = document.getElementById('perm_methods');

    // Find the methods for the selected class.
    var cls = objects[objects.selectedIndex].value;
    var mets = null;
    for (i = 0; i < perm_methods.length; i++) {
        if (perm_methods[i].cls == cls) {
            mets = perm_methods[i].methods;
            break;
        }
    }

    // Clear methodlist.
    for (i = methods.length-1; i >= 0; i--)
        methods.remove(i);
    
    if (mets == null) { alert('error, no methods for '+cls); return; }

    // Update methodlist.
    for (i = 0; i < mets.length; i++) {
        style = mets[i].rem ? 'color:red;' : null
        if (!mets[i].cur)
            Perm_add_option(methods, mets[i].name, null, null, style);
    }
    
    if (methods.length == 0) { Perm_add_option(methods, "", "-- Empty --"); }

    Perm_methods_change(); // Make sure the all link has correct text.
}

// Update ...
function Perm_current_change() {
}

// Create an option.
function Perm_create_option(value, text, selected, style) {
    var new_elm = document.createElement('option');
    new_elm.text = text == null ? value : text;
    new_elm.value = value;
    new_elm.selected = selected ? true : false;
    if (style) { new_elm.style = style; }
    return new_elm;
}

// Create and add an option to the select.
function Perm_add_option(select, value, text, selected, style) {
    elm = Perm_create_option(value, text, selected, style);
    try {
        select.add(elm, null); // standards compliant; doesnt work in IE
    } catch(ex) {
        select.add(elm); // IE only
    }
}

// Add an method to current list of methods.
function Perm_add() {
    var current = document.getElementById('perm_current');
    var objects = document.getElementById('perm_objects');
    var methods = document.getElementById('perm_methods');
    var color = "color:green;"

    // Find selected.
    var cls = objects[objects.selectedIndex].value;
    var mets = new Array();
    for (i = 0; i < methods.length; i++)
        if (methods[i].selected) { mets[mets.length] = methods[i].value; }

    if (mets.length == 0) { return; } // No methods selected

    // Add selected to current.
    for (i = 0; i < mets.length; i++) {
        m = Perm_find_method(cls, mets[i]);
        m.cur = true;
        
        for (index = 0; index < current.length; index++)
            if (current[index].value == cls) break;
        
        adjust = (index == current.length) ? 2 : 1;
        opt = Perm_create_option(cls+m.name+m.id, "- "+m.name, null, color);
        for (j = current.length-1; j >= 0; j--) {
            current[j+adjust] = current[j].cloneNode(true);
            
            if (adjust == 2 && j == 0) {
                current[0] = Perm_create_option(cls);
                current[1] = opt;
            } else if (j == index+1) {
                current[j] = opt;
                break;
            }
        }
    }

    // Remove selected from methods.
    for (i = methods.length-1; i >= 0; i--)
        if (methods[i].selected) { methods.remove(i); }
    
    if (methods.length == 0) { Perm_add_option(methods, "", "-- Empty --"); }
}

function Perm_rem() {
    var current = document.getElementById('perm_current');
    var objects = document.getElementById('perm_objects');
    var methods = document.getElementById('perm_methods');
    var color = "color:red;"
    
    alert("error: not implemented yet.");
}

