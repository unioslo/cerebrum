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

cereweb.worklist = function(title, container, options) {
    this.title = title;
    this.container = YD.get(container);
    this.options = options;

    this.buildWidget();
    this.initializeBehaviour();
    this.populate();
}

cereweb.worklist.prototype = {
    events: {
        worklistChanged: new YAHOO.util.CustomEvent("worklistChanged"),
        selectionChanged: new YAHOO.util.CustomEvent("selectionChanged")
    },
    types: [],
    buildWidget: function() {
        // This could be replaced with an AJAX fetch of the worklist template.
        // However, it works fine now so I'll leave it as it is.
        this._items = {};

        YD.addClass(this.container, 'worklist');
        var title = document.createElement('h2');
        title.innerHTML = this.title;
        this.container.appendChild(title);
        var form = document.createElement('form');
        form.setAttribute('method', 'post');
        this.container.appendChild(form);
        this.form = form;
        
        var div = document.createElement('div');
        YD.addClass(div, 'buttons');
        form.appendChild(div);
        var buttons = [
            ['All', 'select_all'],
            ['None', 'select_none'],
            ['Invert', 'invert_selection'],
            ['Forget', 'forget_selected']
        ];
        for (var i=0; i < buttons.length; i++) {
            var button = document.createElement('button');
            button.innerHTML = buttons[i][0];
            button.setAttribute('name', buttons[i][1]);
            div.appendChild(button);
        };

        div = document.createElement('div');
        YD.addClass(div, 'list');
        var list = document.createElement('select');
        list.setAttribute('multiple', 'multiple');
        list.setAttribute('size', 6);
        this.list = list;
        div.appendChild(list);
        form.appendChild(div);
        this.emptyElm = {id: -1, name: "-Remembered objects-", type: '' };
        this.add(this.emptyElm);

        div = document.createElement('div');
        YD.addClass(div, 'actions');
        this.actions = div;
        form.appendChild(div);
    },
    initializeBehaviour: function() {
        this.ajaxUpdater.scope = this;
        this.actionUpdater = new cereweb.callbacks.htmlSnippet(this, 'addAction');
        YE.on(this.form, 'click', this.onClick, this, true);
        YE.on(this.form, 'change', this.onChange, this, true);
        cereweb.action.add('worklist/remember', this.remember, this);
        this.events.worklistChanged.subscribe(this.updateLinks, this, true);
        this.events.selectionChanged.subscribe(this.updateSelection, this, true);
        cereweb.events.pageChanged.subscribe(this.updateLinks, this, true);
    },
    updateLinks: function(event, args) {
        var rememberLinks = YD.getElementsBy(this.isRememberLink, 'a', 'container');
        for (var i=0; i<rememberLinks.length; i++) {
            var link = rememberLinks[i];
            var id = cereweb.utils.getParam(unescape(link.href), 'id');
            if (this.get(id))
                link.innerHTML = 'forget';
            else
                link.innerHTML = 'remember';
        }
    },
    populate: function() {
        var url = this.options.populate_url;
        var cObj = YC.asyncRequest('GET', url, this.ajaxUpdater);
    },
    isRememberLink: function(el) {
        if (el.nodeName.toUpperCase() !== 'A')
            return false;
        if (el.pathname.search('worklist/remember') == -1)
            return false;
        return true;
    },
    ajaxUpdater: {
            success: function(o) {
                try {
                    var obj = eval('(' + o.responseText + ')');
                    if (obj.result === 'success') {
                        if (obj.objects) {
                            for (var i=0; i<obj.objects.length; i++)
                                this.add(obj.objects[i], true);
                            this.events.selectionChanged.fire();
                        }
                    } else
                        cereweb.msg.warn('Could not update worklist.');
                } catch(ex) {
                    if (this.options.errorHandler)
                        this.options.errorHandler(o);
                }
            },
            failure: function(o) {
                cereweb.msg.warn('Could not update worklist.');
                if (this.options.errorHandler)
                    this.options.errorHandler(o);
            }
    },
    get: function(id) {
        return this._items[id];
    },
    add: function(obj, quiet) {
        var duplicate = !!this._items[obj.id];
        if (duplicate)
            return false;

        if (YAHOO.lang.isUndefined(obj.type) ||
            YAHOO.lang.isUndefined(obj.name)) {
            var url = this.options.add_url;
            var args = 'ids='+obj.id;
            var cObj = YC.asyncRequest('POST', url, this.ajaxUpdater, args);
            return true; // Method will be called again when server responds.
        }
            
        this._items[obj.id] = obj;
        this.addToSelect(obj);
        
        // Remove the dummy element if it's in the list.
        if (this.list.length == 2 && this.list.item(0).value == -1)
            this.remove(-1);

        this.events.worklistChanged.fire(obj.id);
        return true;
    },
    remove: function(id, quiet) {
        var exists = !!this._items[id];
        if (exists)
            delete this._items[id];

        var removed = false;
        if (exists || id == -1) { // Dummy is never in _items
            for (var i=0; i<this.list.length; i++) {
                var elm = this.list[i];
                if (elm.value == id) {
                    this.list.remove(i);
                    removed = true;
                    break;
                }
            }
        }
        if (this.list.length == 0)
            this.add(this.emptyElm);

        if (!quiet && id != -1) {
            var url = this.options.remove_url;
            var args = 'ids='+id;
            var cObj = YC.asyncRequest('POST', url, this.ajaxUpdater, args);
        }

        this.events.worklistChanged.fire(id);
        return removed;
    },
    addToSelect: function (obj) {
        var elm = document.createElement('option');
        if (obj.selected)
            elm.setAttribute('selected', 'selected');
        elm.value = obj.id;
        var str = '';
        if (obj.type)
            str = obj.type + ': '
        elm.innerHTML = str + obj.name;

        try { // standards compliant; doesnt work in IE
            this.list.add(elm, null);
        } catch(ex) { // IE only
            this.list.add(elm); 
        }
    },
    remember: function(name, args) {
        var event = args[0];
        YE.preventDefault(event);
        var obj = args[1];
        this.add(obj) || this.remove(obj.id);
    },
    updateSelection: function() {
        var selected = new Array();
        var list = this.list;
        for (var i = 0; i < list.length; i++) {
            if (list[i].selected) selected.push(list[i].value);
        }
      
        var args = "ids=" + selected;
        var url = this.options.select_url;
        var cObj = YC.asyncRequest('POST', url, this.ajaxUpdater, args);
        
        this.selected = selected;
        this.updateActions();
    },
    getSelected: function() {
        return this.selected;
    },
    updateActions: function() {
        // Hide all actions.
        var actions = this.actions.childNodes;
        if (actions.length > 0)
            YD.setStyle(actions, 'display', 'none');
      
        var type = this.get_type(this.selected);
        var action = this.get_action(type);
        if (action) {
            YD.setStyle(action, 'display', 'block');
        }
        // Else: An action is being downloaded.  This method will be rerun
        // when the action is available.
    },
    onClick: function(e, args) {
        var target = YE.getTarget(e);
        if (target.tagName.toUpperCase() === 'BUTTON') {
            YE.preventDefault(e);
            this[target.name]();
        } else if (target.tagName.toUpperCase() === 'A') {
            target.search = target.search.replace('_id_', this.getSelected());
        }
    },
    onChange: function(e, args) {
        var target = YE.getTarget(e);
        if (target.tagName.toUpperCase() === 'SELECT') {
            this.events.selectionChanged.fire();
        }
    },
    select_all: function () {
        for (var i = 0; i < this.list.length; i++) {
            this.list[i].selected = true;
        }
        this.events.selectionChanged.fire();
    },
    select_none: function () {
        for (var i = 0; i < this.list.length; i++) {
            this.list[i].selected = false;
        }
        this.events.selectionChanged.fire();
    },
    invert_selection: function () {
        for (var i = 0; i < this.list.length; i++) {
            this.list[i].selected = !this.list[i].selected;
        }
        this.events.selectionChanged.fire();
    },
    forget_selected: function () {
        for (var i=0; i < this.selected.length; i++)
            this.remove(this.selected[i]);
        this.events.selectionChanged.fire();
    },
    get_type: function(ids) {
        if (ids.length == 0)
            return 'none';

        // We don't have indexOf, so use string.search.
        // This is probably close to n^2 but we expect
        // small lists so it shouldn't matter.
        var types = [];
        for (var i=0; i<ids.length; i++) {
            var current = types.join('');
            var t = this.get(ids[i]).type;
            // A type of 'personperson' makes sense.  This means multiple
            // persons have been selected.  However, personpersonperson
            // is redundant.
            if (current.search(t+t) == -1) {
                types.push(t);
                types = types.sort(YAHOO.util.Sort.compareAsc);
            }
        }
        return types.join("");
    },
    get_action: function (type) {
        return this.types[type] || this.create_action(type);
    },
    create_action: function (type) {
        // Replaces the regex with value in the action.
        var url = this.options.template_url;
        var args = "type=" +type;
        this.actionUpdater.argument = type; // Set args.
        var cObj = YC.asyncRequest('POST', url, this.actionUpdater, args);
        return false;
    },
    addAction: function(html, type) {
        var action = document.createElement('div');
        action.innerHTML = html.replace('_class_', type);
        YD.setStyle(action, 'display', 'none');
        this.actions.appendChild(action);
        this.types[type] = action;
        this.updateActions();
    }
}
YE.onAvailable('worklist', function() { 
    this.innerHTML = ''; // Disable old worklist.
    new cereweb.worklist('Worklist', 'worklist', {
        populate_url: '/worklist/get_all',
        add_url: '/worklist/add',
        remove_url: '/worklist/remove',
        select_url: '/worklist/select',
        template_url: '/worklist/template'
    }) 
});

if(cereweb.debug) {
    log('worklist is loaded');
}
