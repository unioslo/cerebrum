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

// Initialize yui-stuff.
YAHOO.namespace('cereweb');
YAHOO.widget.Logger.enableBrowserConsole();

// Shorthand
log = YAHOO.log;
YD = YAHOO.util.Dom; 
YE = YAHOO.util.Event;
YC = YAHOO.util.Connect;
cereweb = YAHOO.cereweb;

/**
 * Set the cereweb.debug variable to true to enable the YUI logger widget.
 * Useful for IE debugging.  Firebug is better though.
 */
cereweb.debug = false;
if(cereweb.debug) {
    YE.onAvailable("container", function(o) {
        var logger = cereweb.createDiv('logger');
        var myLogReader = new YAHOO.widget.LogReader(logger);
        debugger /* Force the debugger to break. */
    });
};

cereweb.createDiv = function (id, parent) {
    if (YAHOO.lang.isUndefined(parent))
        parent = document.body;
    else if (YAHOO.lang.isString(parent))
        parent = YD.get(parent);
    var el = document.createElement('div');

    if (YAHOO.lang.isString(id))
        el.setAttribute('id', id);

    parent.appendChild(el);
    return el;
}

/**
 * Some basic event handling.  Currently it only handles click events on
 * links.  To register a link, use cereweb.action.add.
 */
cereweb.action = {
    /** This object is private and should not be accessed directly. */
    _events: {},
    /**
     * To register (overload) a link target, provide the name of the link
     * target and a function that should be called when a link with this
     * target is clicked.
     *
     * The callback function is called with two arguments:
     *   name: The name of the target that was clicked.
     *   args: An array of extra arguments.
     *   args[0]: The click event that triggered our event.
     *   args[1]: The arguments we parsed from the link.
     */
    add: function(name, func, obj) {
        var event = this._events[name] || new YAHOO.util.CustomEvent(name);
        event.subscribe(func, obj, true);
        this._events[name] = event;
    },
    fire: function(event, action) {
        if (this._events[action.name])
            this._events[action.name].fire(event, action.args);
        else {
            var subaction = '*/' + action.name.split('/')[1];
            if (this._events[subaction])
                this._events[subaction].fire(event, action.args);
        }
    },
    parse: function(url) {
        var url = unescape(url.replace(/http.*\/\/.*?\//,''))
        var anchor = url.split('#');
        if (anchor.length > 1)
            url = anchor[1];
        var target = url.split('?');
        var elms = (target[1] || '').split('&');
        var args = {};

        for (var i = 0; i < elms.length; i++) {
            var x = elms[i].split('=');
            args[x[0]] = x[1];
        }
            
        return {'name': target[0], 'args': args};
    },
    clicked: function(e) {
        var target = YE.getTarget(e);

        if (target.nodeName.toLowerCase() === 'a') {
            var action = this.parse(target.href);
            this.fire(e, action);
        }
    }
}
YE.addListener('container', "click", cereweb.action.clicked,
    cereweb.action, true);

/**
 * This object creates dialogues of divs with both the "box" and the "edit"
 * classes.  It also adds links to the actions div so that the box can be
 * shown.
 */
cereweb.editBox = {
    /* boolean function used to recognize editBoxes */
    isEditBox: function(el) {
        return YD.hasClass(el, 'box') &&
               YD.hasClass(el, 'edit');
    },
    /* parses the DOM and runs add on all editBoxes it finds */
    init: function() {
        var els = YD.getElementsBy(
            this.isEditBox, 'div', 'content');
        if (els.length > 0)
            YD.batch(els, this.add, this, true);
    },
    /**
     * transforms the element to a YAHOO Dialog, and adds a link to the
     * actions div that, when clicked, shows the dialog
     */
    add: function(el) {
        if (!el.id)
            YD.generateId(el, 'editBox_');

        var id = el.id;
        var header = el.getElementsByTagName('h3')[0];

        el.removeChild(header);

        var editBox = new YAHOO.widget.Dialog(el, {
            'width': '600px',
            'draggable': true,
            'visible': false,
            'fixedcenter': true,
            'postmethod': 'form' });
        editBox.setHeader(header.innerHTML);
        editBox.render();
        editBox.hide();
        el.style.display = "";

        var link = document.createElement('a');
        link.href = "#" + el.id;
        link.innerHTML = header.innerHTML;

        var actions = YD.get('actions');
        var list = actions.getElementsByTagName('ul');
        if (list) {
            list = list[0];
            var li = document.createElement('li');
            li.appendChild(link);
            list.appendChild(li);
        } else {
            actions.appendChild(link);
            actions.appendChild(document.createElement('br'));
        }

        cereweb.action.add(id, this.toggle, editBox);
        var cancel_links = YD.getElementsByClassName("cancel", null, el);
        if (cancel_links.length > 0)
            YE.addListener(cancel_links, 'click', editBox.hide, editBox, true);
    },
    /**
     * toggle the dialogues visibility.
     */
    toggle: function(event) {
        YE.preventDefault(event);
        if (this.element.style.visibility !== "visible")
            this.show();
        else
            this.hide();
    }
}
YE.onAvailable('content', cereweb.editBox.init, cereweb.editBox, true);

cereweb.tooltip = {
    init: function() {
        var els = YD.getElementsByClassName('tt', null, 'container');
        for (var i=0; i<els.length; i++)
            els[i].setAttribute('title', els[i].nextSibling.innerHTML);
        this.tt = new YAHOO.widget.Tooltip('tt', {context:els});
    }
}

/**
 * Some text and links are only to be shown to users without javascript,
 * and some text and links should only be shown to users with it.
 */
cereweb.javascript = {
    init: function() {
        var nojs = YD.getElementsByClassName('nojs', null, 'container');
        var jsonly = YD.getElementsByClassName('jsonly', null, 'container');
        if (nojs.length > 0) { YD.setStyle(nojs, "display", "none"); }
        if (jsonly.length > 0) { YD.setStyle(jsonly, "display", ""); }
        cereweb.tooltip.init();
    }
}
YE.onAvailable('container', cereweb.javascript.init);

cereweb.tabs = new YAHOO.widget.TabView('tabview');
cereweb.tabs.DOMEventHandler = function(e) { /* do nothing */ };

if(cereweb.debug) {
    log('bases are loaded');
}
