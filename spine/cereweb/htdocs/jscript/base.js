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

/** Cereweb Actions
 *
 * In this script we listen to the window.load event, and when this is raised,
 * we listen for the click event on all links with class action.  When such an
 * event occur, we call the actionClicked function.
 * 
 * This function parses the link that has been clicked with the parseAction
 * function.  This gives us the name of the link and the arguments.  For
 * instance 'edit_motd' with id=133.
 *
 * Enter the cereweb.actions object.  This can be thought of as a hash
 * containing functions.  We use the name of the link that has been clicked and
 * checks if the cereweb.actions object contains such an attribute.  If it
 * does, we call that action with the arguments we found.
 *
 * Example:
 *   cereweb.actions['test'] = function(event, args) {
 *       if (cereweb.can_do_action) {
 *           YE.preventDefault(event); // Do not follow link.
 *           handleLink(args);         // We do it here.
 *       }
 *   }
 *
 * Note that if the action doesn't call YE.preventDefault, the web browser will
 * follow the link.
 */

cereweb.actions = { };

// Parse a link to help us look it up in the actions object.
function parseAction(url) {
    url = unescape(url.replace(/http.*\/\/.*?\//,''))
    var target = url.split('?');
    var args = {};
    var elms = (target[1] || '').split('&');
    for (var i = 0; i < elms.length; i++) {
        var x = elms[i].split('=');
        args[x[0]] = x[1];
    }
    return {'name': target[0], 'args': args};
};

// When actionClicked is called, check if what was clicked
// was a link and, if is was, look it up in the actions object.
// If it exists, run it.
function actionClicked(e) {
    var target = YE.getTarget(e);
    if (target.nodeName.toLowerCase() === 'a') {
        var action = parseAction(target.href);
        var name = action.name;
        var args = action.args;
        cereweb.actions[name] && cereweb.actions[name](e, args);
    }
};
YE.addListener('maindiv', "click", actionClicked);

/**
 * Some text and links are only to be shown to users without javascript,
 * and some text and links should only be shown to users with it.
 */
function initJS() {
    var nojs = YD.getElementsByClassName('nojs', null, 'maindiv');
    var jsonly = YD.getElementsByClassName('jsonly', null, 'maindiv');
    if (nojs.length > 0) { YD.setStyle(nojs, "display", "none"); }
    if (jsonly.length > 0) { YD.setStyle(jsonly, "display", ""); }

};
YE.onAvailable('maindiv', initJS);

/**
 * Adds a link to the element in the actions div.  Pressing this link
 * toggles the elements visibility.
 */
function addOptional(el) {
    // Make sure the element has an id we can refer to.
    if (!el.id)
        YD.generateId(el, 'optional_');

    var actions = YD.get('actions');
    var text = el.getElementsByTagName('h3')[0].innerHTML;
    var link = document.createElement('a');
    var br = document.createElement('br');

    link.href = "#" + el.id;
    link.innerHTML = text;
    actions.appendChild(link);
    actions.appendChild(br);

    var cancel_links = YD.getElementsByClassName("cancel", null, el);
    if (cancel_links.length > 0)
        YE.addListener(cancel_links, 'click', cereweb.flip, el, true);

    YE.addListener(link, 'click', cereweb.flip, el, true);
}
function initOptional() {
    var optional = YD.getElementsByClassName('edit', 'div', 'maindiv');
    if (optional.length > 0) {
        YD.batch(optional, addOptional);
    }
}
YE.onAvailable('maindiv', initOptional);

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

/**
 * Flip the visibility of an element.
 */
cereweb.flip = function() {
    if (this.style.display === 'none') {
        this.style.display = '';
    } else {
        this.style.display = 'none';
    }
};
