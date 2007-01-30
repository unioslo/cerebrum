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

var cerebug = false;
if(cerebug) {
    YAHOO.util.Event.onAvailable("logger", function(o) {
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
                YAHOO.util.Event.addListener(element, 'click', func);
            }
        }
    }
}
// Flip the visibility (display-value) on the selected element.
function FV_flip(elm) {
    for (var i = 0; i < FV_elements[elm].length - 2; i++) {
        if (FV_elements[elm][i] != null) {
            e = document.getElementById(FV_elements[elm][i]);
            YAHOO.cereweb.flip(e);
        }
    }
}
YAHOO.cereweb.flip = function(e) {
    if (e.style.display === 'none') {
        e.style.display = '';
    } else {
        e.style.display = 'none';
    }
};
YAHOO.util.Event.addListener(window, 'load', FV_init_listeners);
