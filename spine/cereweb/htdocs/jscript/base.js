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

// When an action gets clicked, look it up in the
// actions object and run it.
function actionClicked(e) {
    var action = parseAction(YE.getTarget(e).href);
    var name = action.name;
    var args = action.args;
    cereweb.actions[name] && cereweb.actions[name](e, args);
};

// When the document has loaded, find all "action" links
// in the document and make them run the actionClicked
// event when they are clicked.
YE.addListener(window, 'load', function(e) {
    var actions = YD.getElementsByClassName('action', 'a');
    YD.batch(actions, function(el) {
        // We hide javascript only actions from non-javascript browsers
        // by setting their style="display: none;"
        if (el.style && el.style.display && el.style.display == 'none')
            el.style.display = '';
        YE.addListener(el, "click", actionClicked);
    });
});

var cerebug = false;
if(cerebug) {
    YE.onAvailable("logger", function(o) {
        var myLogReader = new YAHOO.widget.LogReader("logger");
    });
};

// Cross-browser method to set text on a Anchor DOM-object.
function set_link_text(obj, text) {
    if (obj) {
        obj.replaceChild(document.createTextNode(text), obj.firstChild);
    }
}

/* Flip visibility */
// Contains the diffrent divs and their links/buttons.
var FV_elements = new Array();
// Register a division which should have its visibility flipped
// when link and/or button is pressed.
function FV_register(div, link, link_div, button, button_div) {
    var i = FV_elements.length < 1 ? 0 : FV_elements.length;
    FV_elements[i] = new Array(div, link_div, button_div, link, button);
}
// Initialize listeners on links and/or buttons in FV_elements.
function FV_init_listeners() {
    for (var i = 0; i < FV_elements.length; i++) {
        var length = FV_elements[i].length;
        for (var j = length - 2; j < length; j++) {
            if (FV_elements[i][j] != null) {
                element = document.getElementById(FV_elements[i][j]);
                func = new Function("FV_flip("+i+");");
                YE.addListener(element, 'click', func);
            }
        }
    }
}
// Flip the visibility (display-value) on the selected element.
function FV_flip(elm) {
    for (var i = 0; i < FV_elements[elm].length - 2; i++) {
        if (FV_elements[elm][i] != null) {
            e = document.getElementById(FV_elements[elm][i]);
            cereweb.flip(e);
        }
    }
}
cereweb.flip = function(e) {
    if (e.style.display === 'none') {
        e.style.display = '';
    } else {
        e.style.display = 'none';
    }
};
YE.addListener(window, 'load', FV_init_listeners);
