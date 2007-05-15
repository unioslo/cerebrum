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


cereweb.worklist = {
    init: function() {
        this.init_actions();
        this.init_objects();

        // This method is called when the user clicks on a link that
        // points to /remember_link.  These links shouldn't be visible
        // unless javascript is enabled.
        cereweb.action.add('worklist/remember', this.remember_wrapper, this);
        this.worklistChanged.subscribe(this.update_actions, this, true);
    },
    remember_wrapper: function(name, args) {
        var event = args[0];
        args = args[1];

        YE.preventDefault(event);
        var t = YE.getTarget(event);
        this.remember(args['id'], args['type'], args['name']);
    },
    // method to add an entity to the worklist.
    remember: function remember(id, cls, name) {
        var worklist = document.getElementById('WL_select');

        if (cereweb.worklist.objects[id]) { // Object already remembered: remove
            this.forget(id);
        } else {
            if (worklist.length >= cereweb.worklist.config.max_objects) {
                alert("Cannot add any more objects to the worklist.");
                return;
            }

            // Remove option -Remembered objects-
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

            // Change the text on the element by id
            var link = document.getElementById('WL_link_'+id);
            if (link)
                link.innerHTML = "forget";

            // Tell the server that we have added an element.
            var add_url = '/worklist/add';
            args = "id="+id+"&cls="+cls+"&name="+name
            var cObj = YC.asyncRequest('POST', add_url, cereweb.worklist.callback, args);
        }
    },
    forget: function (id) {
        var worklist = document.getElementById('WL_select');
        delete cereweb.worklist.objects[id];
        for (var i = 0; i < worklist.length; i++) {
            if (worklist[i].value === id) {
                worklist.remove(i);
                break;
            }
        }

        if (worklist.length == 0) {
            var option = document.createElement('option');
            option.text = "-Remembered objects-";
            worklist[0] = option;
        }

        // change the text on the element by id
        var link = document.getElementById('WL_link_'+id)
        if (link)
            link.innerHTML = "remember";

        var action = YD.get('WL_action_' + id);
        if (action && action.parentNode)
            action.parentNode.removeChild(action);

        // tell the server that we have removed some element.
        var remove_url = '/worklist/remove';
        var args = "id="+id;
        var cObj = YC.asyncRequest('POST', remove_url, cereweb.worklist.callback, args);
    },
    // Remove selected items from worklist
    forget_selected: function () {
        var worklist = document.getElementById('WL_select')
        for (var j = 0, i = worklist.length-1; i >= 0; i--) {
            if (worklist[i].selected &&
                worklist[i].text !== "-Remembered objects-")
                    this.forget(worklist[i].value);
        }
    },
    select_all: function () {
        var worklist = document.getElementById('WL_select')
        for (var i = 0; i < worklist.length; i++) {
            worklist[i].selected = true;
        }
    },
    select_none: function () {
        var worklist = document.getElementById('WL_select')
        for (var i = 0; i < worklist.length; i++) {
            worklist[i].selected = 0;
        }
    },
    invert_selection: function () {
        var worklist = document.getElementById('WL_select')
        for (var i = 0; i < worklist.length; i++) {
            if (worklist[i].selected == 1) {
                worklist[i].selected = 0;
            } else {
                worklist[i].selected = 1;
            }
        }
    },
    config: {
        max_objects: 20,
    },
    actions: {
        'WL_all': 'select_all',
        'WL_none': 'select_none',
        'WL_invert': 'invert_selection',
        'WL_forget': 'forget_selected',
        'WL_select': 'update_actions'
    },
    // types : [((ids), action_name, action), ...]
    types: [],
    // This is where we store the information about our objects.
    objects: {},
    worklistChanged: new YAHOO.util.CustomEvent('worklistChanged', this),
    callback: {
        success: function(o) { 
                var obj = eval('(' + o.responseText + ')');
                cereweb.worklist.objects = obj;
        },
        failure: this.error,
        timeout: 5000
    },
    handler: function (event) {
        var target = YE.getTarget(event);
        var tag = target.nodeName.toLowerCase();
        // Links are handled by actionClicked.
        if (tag !== 'a') {
            var action = this.actions[target.id];
            if (action && this[action])
                this[action](event);
            this.worklistChanged.fire();
        }
    },
    // Fill cereweb.worklist.objects and change link-texts to forget.
    init_objects: function () {
        var worklist = YD.get('WL_select');

        for (var i = 0; i < worklist.options.length; i++) {
            var opt_name = worklist.options[i].text.split(':', 2);
            var id = worklist.options[i].value;
            var type = opt_name[0];
            var name = opt_name[1];

            // Fill cereweb.worklist.objects with the info already in the worklist
            cereweb.worklist.objects[id] = {'id': id, 'type': type, 'name': name};

            // change the text on links to forget for things already in the worklist
            var link = document.getElementById('WL_link_'+id);
            if (link)
                link.innerHTML = "forget";
        }
    },
    init_actions: function () {
        var worklist = document.getElementById('WL_select');
        for (var i = 0; i < worklist.length; i++) {
            if (worklist[i].selected) {
                cereweb.worklist.worklistChanged.fire(true);
                break;
            }
        }
    },
    update_actions: function (event, args) {
        if (event === "worklistChanged")
            var update_only = args[0];
        else
            var update_only = event || false;

        var worklist = YD.get('WL_select');
        var ids = new Array();
        var j = 0;
        for (var i = 0; i < worklist.length; i++) {
            if (worklist[i].selected &&
                worklist[i].text !== "-Remembered objects-") {
                    ids[j++] = worklist[i].value;
            }
        }
      
        var args = "ids=" + ids;
        var update_url = '/worklist/selected';
        
        if (!update_only) {
            var cObj = YAHOO.util.Connect.asyncRequest('POST',
                update_url, cereweb.worklist.callback, args);
        }
        
        // Hide all actions.
        YD.setStyle(YD.getElementsByClassName('wl_action'), 'display', 'none');
      
        // Show (or create and then show) the action for the selected items.
        if (ids.length > 0) {
            ids = ids.sort(function (a, b) { return (a - b); });
            var action = YD.get('WL_action_' + ids);
            if (!action) {
                action = this.get_action(ids);
                var actions = document.getElementById('wl_actions');
                actions.appendChild(action);
            }
        } else {
            var action = document.getElementById('WL_action_info');
        }
        action.style.display = "block";
    },
    // Returns an action for the array with selected items.
    // Show errors to the user, in a inobtrusive way.
    error: function (o) {
        msg = o.statusText;
        var action_div = document.getElementById('wl_actions');
        var error_div = document.getElementById('WL_errors');

        // hide all actions
        var actions = document.getElementById('wl_actions');
        for (var i = 0; i < actions.childNodes.length; i++) {
            if (actions.childNodes[i].style) {
                actions.childNodes[i].style.display = "none";
            }
        }

        error_div.style.display = "block";
        error_div.lastChild.nodeValue = msg;
    },
    get_action: function (ids) {
        return this.types[ids] || this.create_action(ids);
    },
    // Creates an action for the array with selected items.
    create_action: function (ids) {

        // Clones an action
        var clone_action = function (name, action_id) {
            var action = document.getElementById('WL_action_'+name.toLowerCase());
            if (action == null) {
                action = document.getElementById('WL_action_default');
            }
            
            var new_action = action.cloneNode(true);
            new_action.id = "WL_action_"+action_id;
            return new_action;
        }

        // Check if selected classes fits a pattern.
        var is_match = function (first, rest, selected) {
            if (selected[0][1].toLowerCase() != first) {
                return false;
            } else if (rest == null) {
                if (selected[1][1].toLowerCase() != first) {
                    return true;
                } else {
                    return false;
                }
            }

            for (var i = 1; i < selected.length; i++) {
                if (selected[i][1].toLowerCase() != rest) {
                    return false;
                }
            }
            return true;
        }

        if (ids.length === 1) {
            var id = ids[0];
            var cls = cereweb.worklist.objects[id].type;
            var name = cereweb.worklist.objects[id].name;
            action = clone_action(cls, id);
        } else if (is_match("person", null, ids)) {
            action = clone_action("person", ids);
        } else if (is_match("group", "account", ids)) {
            action = clone_action("group", ids);
        } else {
            name = "Error";
            var cls = cereweb.worklist.objects[ids[0]].type;
            for (var i = 1; i < ids.length; i++) {
                cls += ", "+cereweb.worklist.objects[ids[i]].type;
            }
            action = clone_action("default", ids);
        }
        
        // Replaces the regex with value in the action.
        var replace_html = function (action, regex, value) {
            action.innerHTML = action.innerHTML.replace(regex, value);
        }

        // replace the variables in the actionbox.
        replace_html(action, /_id_/g, id);
        replace_html(action, /_class_/g, cls);
        replace_html(action, /_name_/g, name);
        
        // add the new action to cereweb.worklist.types
        cereweb.worklist.types[cereweb.worklist.types.length] = new Array(ids, action);
        return action;
    }
}
YAHOO.util.Event.addListener('worklist', 'click', cereweb.worklist.handler, cereweb.worklist, true);
YAHOO.util.Event.addListener('worklist', 'change', cereweb.worklist.handler, cereweb.worklist, true);
YAHOO.util.Event.onAvailable('WL_select', cereweb.worklist.init, cereweb.worklist, true);

if(cerebug) {
    log('worklist is loaded');
}
