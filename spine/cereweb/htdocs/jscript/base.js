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
* Cereweb events.
*/
cereweb.events = {
    pageChanged: new YAHOO.util.CustomEvent('pageChanged'),
    sessionError: new YAHOO.util.CustomEvent('sessionError')
};
/**
* Reusable AJAX callbacks.
*/
cereweb.callbacks = {
    /**
     * This snippet tries to extract the 'content' div.
     * Finally it calls this.update(result).
     */
    htmlSnippet: function(scope, cfn, cfa, failure) {
        // Name of function to call with the resulting html.
        this.scope = scope;
        this.scope.__htmlSnippet_cfn = cfn;
        this.argument = cfa;
        this.failure = failure;
    }
}

cereweb.callbacks.htmlSnippet.prototype = {
    success: function(o, args) {
        var begin = '<div id="content">';
        var end = '</div>';
        var a, b; // Start and stop indexes of the content div.
        var r = o.responseText; // Make a 

        a = r.search(begin) + begin.length; // We don't include the div tag.
        b = a; // The end can't be before the beginning :)
        r = r.substring(a, r.length);

        var x, y;
        var i = 1; 
        while (i > 0) { // While we're inside the content div.
            x = r.search(end);
            y = r.search('<div'); 
            if (x < y || y < 0) {
                i -= 1;
            } else {
                i += 1;
                x = y;
            }
            b += x; // Advance the end, don't include the end tag.
            // substring has no offset, so eat the part we just found.
            r = r.substring(x + 1, r.length);
        }
        r = o.responseText.substring(a, b);
        var cfn = this.__htmlSnippet_cfn;
        this[cfn](r, o.argument);
    }
}

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

cereweb.utils = {
    createDiv: function (id, parent) {
        if (YAHOO.lang.isUndefined(parent))
            parent = document.body;
        else if (YAHOO.lang.isString(parent))
            parent = YD.get(parent);
        var el = document.createElement('div');

        if (YAHOO.lang.isString(id))
            el.setAttribute('id', id);

        parent.appendChild(el);
        return el;
    },
    getParam: function gup(url, name) {
        name = name.replace(/[\[]/,"\\\[").replace(/[\]]/,"\\\]");
        var regexS = "[\\?&]"+name+"=([^&#]*)";
        var regex = new RegExp(regexS);
        var results = regex.exec(url);
        if(results == null)
            return "";
        else
            return results[1];
    }
}
cereweb.createDiv = cereweb.utils.createDiv; // Backwards compatibility.

cereweb.msg = {
    _msg: function(message, level, timeout) {
        var messages = YD.get('messages');
        var p = document.createElement('p');
        YD.addClass(p, level);
        p.innerHTML = message;
        messages.appendChild(p);
        var fn = function() {
            messages.removeChild(p);
        }
        window.setTimeout(fn, timeout);
    },
    error: function(message) {
        cereweb.msg._msg(message, 'error', 10000);
    },
    warn: function(message) {
        cereweb.msg._msg(message, 'warn', 5000);
    },
    info: function(message) {
        cereweb.msg._msg(message, 'info', 5000);
    }
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
        if (this._events[action.name]) {
            this._events[action.name].fire(event, action.args);
        } else {
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
    },
    clear: function() {
        this._events = {};
    }
}
YE.addListener('container', "click", cereweb.action.clicked,
    cereweb.action, true);
cereweb.events.sessionError.subscribe(cereweb.action.clear, cereweb.action, true);

/**
 * This object creates dialogues of divs with both the "box" and the "edit"
 * classes.  It also adds links to the actions div so that the box can be
 * shown.
 */
cereweb.editBox = {
    create: function(el, header, body) {
        var editBox = new YAHOO.widget.Dialog(el, {
            'width': '600px',
            'draggable': true,
            'visible': false,
            'fixedcenter': true,
            'postmethod': 'form' });
        if (header)
            editBox.setHeader(header);
        if (body)
            editBox.setBody(body);
        editBox.render();
        editBox.hide();
        return editBox;
    },
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

        var editBox = this.create(el, header.innerHTML);
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
    toggle: function(name, args) {
        var event = args[0];
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

(function() { 
    var inline_edit = function(name, args) {
        var event = args[0];
        YE.preventDefault(event);
        var url = YE.getTarget(event).pathname;
        if (url.slice(0,1) !== '/') // IE doesn't prepend / to url.
            url = '/' + url;
        var arg = args[1].id;

        // Get or create the neccessary divs and dialogues.
        var el = YD.get('edit_' + arg);
        if (el) {
            var myBox = el.obj;
        } else {
            el = cereweb.createDiv('edit_' + arg, 'content');
            var myBox = cereweb.editBox.create(el, 'head', 'body');
            el.obj = myBox;
        }

        myBox.update = function(r) {
            myBox.setBody(r);
            var buttons = YD.getElementsByClassName('buttons', 'div', myBox.element)[0].childNodes;
            for (var i = 0; i < buttons.length; i++) {
                var el = buttons[i];
                if (el.value === 'Cancel')
                    YE.on(el, 'click', function(e) {
                        YE.preventDefault(e);
                        myBox.hide();
                    });
            }
            myBox.show();
        }
        var callback = new cereweb.callbacks.htmlSnippet(myBox, 'update');
        var cObj = YC.asyncRequest('POST',
            url, callback, 'id=' + arg);

    }
    cereweb.action.add('*/edit', inline_edit);
})()

if(cereweb.debug) {
    log('bases are loaded');
}
