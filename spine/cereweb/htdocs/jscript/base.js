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
 * Set the cerebug variable to true to enable the YUI logger widget.
 * Useful for IE debugging.  Firebug is better though.
 */
var cerebug = false;
if(cerebug) {
    YE.onAvailable("maindiv", function(o) {
        logger = document.createElement('div');
        YD.get('maindiv').appendChild(logger);
        var myLogReader = new YAHOO.widget.LogReader(logger);
    });
};

/** Cereweb Actions
 *
 * When a click event occur in our page, we call the cereweb.action.clicked
 * function.
 * 
 * This function check whether the element that was clicked was a link.  If it
 * was, it parses the link with the cereweb.action.parse function.  This gives
 * us the name of the link and the arguments.  For instance 'edit_motd' with
 * id=133.
 *
 * Enter the cereweb.action.actions object.  This can be thought of as a hash
 * containing functions.  We use the name of the link that has been clicked and
 * checks if the cereweb.action.actions object contains such an attribute.  If it
 * does, we call that action with the arguments we found.
 *
 * Example:
 *   cereweb.action.add('test_action'), function(event, args) {
 *       if (can_do_action) {
 *           YE.preventDefault(event); // Do not follow link.
 *           handleLink(args);         // We do it here.
 *       }
 *   });
 *
 * Note that if the action doesn't call YE.preventDefault, the web browser will
 * follow the link.
 */
cereweb.action = {
    actions: {},
    add: function(name, func) {
        this.actions[name] = func;
    },
    parse: function(url) {
        url = unescape(url.replace(/http.*\/\/.*?\//,''))
        var target = url.split('?');
        var args = {};
        var elms = (target[1] || '').split('&');
        for (var i = 0; i < elms.length; i++) {
            var x = elms[i].split('=');
            args[x[0]] = x[1];
        }
        return {'name': target[0], 'args': args};
    },
    /**
     * When actionClicked is called, check if what was clicked
     * was a link and, if is was, look it up in the actions object.
     * If it exists, run it.
     */
    clicked: function(e) {
        var target = YE.getTarget(e);

        if (target.nodeName.toLowerCase() === 'a') {
            var action = this.parse(target.href);
            var name = action.name;
            var args = action.args;
            this.actions[name] && this.actions[name](e, args);
        }
    },
}
YE.addListener('maindiv', "click", cereweb.action.clicked,
    cereweb.action, true);

/**
 * This object takes care of extracting the edit boxes and making
 * them available to the user.
 */
cereweb.editBox = {
    isEditBox: function(el) {
        return YD.hasClass(el, 'box') &&
               YD.hasClass(el, 'edit');
    },
    init: function() {
        var els = YD.getElementsBy(
            this.isEditBox, 'div', 'content');
        if (els.length > 0)
            YD.batch(els, this.add, this, true);
    },
    add: function(el) {
        if (!el.id)
            YD.generateId(el, 'editBox_');

        var id = el.id;
        var header = el.getElementsByTagName('h3')[0];

        el.removeChild(header);

        var editBox = new YAHOO.widget.Dialog(el, {
            'width': '600px',
            'draggable': false,
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
        actions.appendChild(link);
        actions.appendChild(document.createElement('br'));

        YE.addListener(link, 'click', this.show, editBox, true);
        var cancel_links = YD.getElementsByClassName("cancel", null, el);
        if (cancel_links.length > 0)
            YE.addListener(cancel_links, 'click', editBox.hide, editBox, true);
    },
    show: function(event) {
        YE.preventDefault(event);
        this.show();
    }
}
YE.onAvailable('content', cereweb.editBox.init, cereweb.editBox, true);

/**
 * Some text and links are only to be shown to users without javascript,
 * and some text and links should only be shown to users with it.
 */
YE.onAvailable('maindiv', function() {
    var nojs = YD.getElementsByClassName('nojs', null, 'maindiv');
    var jsonly = YD.getElementsByClassName('jsonly', null, 'maindiv');
    if (nojs.length > 0) { YD.setStyle(nojs, "display", "none"); }
    if (jsonly.length > 0) { YD.setStyle(jsonly, "display", ""); }

});
