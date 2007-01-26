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
var perm_original_methods = null; // Contains backup of perm_methods for restore.
var perm_original_current = null; // Contains backup of current for restore.

addLoadEvent(Perm_init_methods);

YAHOO.util.Event.addListener('perm_all', 'click', Perm_methods_all);
YAHOO.util.Event.addListener('perm_add', 'click', Perm_add);
YAHOO.util.Event.addListener('perm_rem', 'click', Perm_rem);
YAHOO.util.Event.addListener('perm_restore', 'click', Perm_restore);
YAHOO.util.Event.addListener('perm_save', 'click', Perm_save);
YAHOO.util.Event.addListener('perm_objects', 'change', Perm_objects_change);
YAHOO.util.Event.addListener('perm_methods', 'change', Perm_methods_change);

YAHOO.util.Event.onAvailable('perm_current', function(e, obj) {
    perm_original_current = obj.cloneNode(true);
});

YAHOO.util.Event.onAvailable(['perm_objects', 'perm_current', 'perm_methods'],
    Perm_methods_load);

function Perm_methods_load() {
    var callback = {
        success: function(o) {
            var objects = document.getElementById('perm_objects');
            var current = document.getElementById('perm_current');
            var methods = document.getElementById('perm_methods');
            var data = eval('(' + o.responseText + ')');
            perm_methods = data.methods;
            perm_original_methods = data.methods;

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
        },
        failure: function(o) { /* empty */ },
        timeout: 5000
    };
    url = '/permissions/get_all_operations'
    var cObj = YAHOO.util.Connect.asyncRequest('GET', url, callback);
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
        color = mets[i].rem ? "red" : null;
        if (!mets[i].cur)
            Perm_add_option(methods, mets[i].name, null, null, color);
    }
    

    Perm_methods_change(); // Make sure the all link has correct text.
    Perm_check_empty(methods);
}

// Create an option.
function Perm_create_option(value, text, selected, color) {
    var new_elm = document.createElement('option');
    new_elm.text = text == null ? value : text;
    new_elm.value = value;
    new_elm.selected = selected ? true : false;
    if (color) { new_elm.style.color = color; }
    return new_elm;
}

// Create and add an option to the select.
function Perm_add_option(select, value, text, selected, color) {
    elm = Perm_create_option(value, text, selected, color);
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
    var color = "green";

    // Find selected.
    var mets = new Array();
    for (i = 0; i < methods.length; i++) {
        if (methods[i].value == "empty") { continue; }
        if (methods[i].selected) { mets[mets.length] = methods[i].value; }
    }

    if (mets.length == 0) { return; } // No methods selected.
    if (current.length == 1 && current[0].value == "empty")
        current.remove(0); // Remove empty option.

    var cls = objects[objects.selectedIndex].value;
    for (index = 0; index < current.length; index++)
        if (current[index].value == cls) break;
        
    // Add selected to current.
    for (i = 0; i < mets.length; i++) {
        m = Perm_find_method(cls, mets[i]);
        m.cur = true;
        
        value = cls + "." + m.name + "." + m.id
        new_option = Perm_create_option(value, "- "+m.name, null, color);

        if (index == current.length) {
            Perm_insert_option(current, new_option, 0);
            Perm_insert_option(current, Perm_create_option(cls), 0);
            index = 0;
        } else {
            Perm_insert_option(current, new_option, index+1);
        }
    }

    // Remove selected from methods.
    for (i = methods.length-1; i >= 0; i--)
        if (methods[i].selected) { methods.remove(i); }
    
    Perm_check_empty(methods);
}

// Remove a method from the current list of methods.
function Perm_rem() {
    var current = document.getElementById('perm_current');
    
    // Update perm_methods and remove from current list.
    for (i = current.length-1; i >= 0; i--) {
        if (current[i] == null || current[i].value == "empty") { continue; }
        if (current[i].selected) {
            str = current[i].value.split(".");
            if (str.length != 3)
                continue
            met = Perm_find_method(str[0], str[1]);
            met.cur = false; met.rem = true;

            if (current[i-1].value.split(".").length == 1 &&
                (current.length == i+1 || 
                 current[i+1].value.split(".").length == 1)
                ) {
                current.remove(i);
                current.remove(i-1); // Remove the class option.
            } else {
                current.remove(i);
            }
        }
    }

    Perm_objects_change(); // Update available method list.
    Perm_check_empty(current);
}

// Restore back to default.
function Perm_restore() {
    var current = document.getElementById('perm_current');
    var objects = document.getElementById('perm_objects');
    
    alert("Restore not implemented yet.");
    return; // todo..
    
    // Restore current list.
    new_node = perm_original_current.cloneNode();
    current.parentNode.replaceChild(new_node, current);

    // Restore method list.
    perm_methods = perm_original_methods;
    
    // Restore objects.
    objects.selectedIndex = 0;
    Perm_objects_change();
}

// Save values to server.
function Perm_save() {
    var form = document.getElementById('perm_form');
    var current = document.getElementById('perm_current');

    for (i = 0; i < current.length; i++)
        current[i].selected = true;
    
    form.submit();
}

// If the select is empty, add an empty-option.
function Perm_check_empty(select) {
    if (select.length == 0)
        Perm_add_option(select, "empty", "-- Empty --");
}

// Fixes an IE bug where insertBefore removes the node text.
function Perm_insert_option(select, new_node, old_index) {
    var text = new_node.text;
    select.insertBefore(new_node, select[old_index]);
    new_node.text = text;
}
