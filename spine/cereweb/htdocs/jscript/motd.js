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

function editMotd(e) {
    var t = YAHOO.util.Event.getTarget(e);
    var content = t.innerText || t.textContent;
    if (t.nodeName.toLowerCase() === 'a' &&
         content === 'edit') {
            var argument = t.href.replace(/.*?id=/,'');
            YAHOO.util.Event.preventDefault(e);
            YAHOO.cereweb.getMotd(argument);
    }
};

function actionClicked(e) {
    var t = YAHOO.util.Event.getTarget(e);
    if (t.nodeName.toLowerCase() === 'a') {
        var action = t.href.split('/').slice(-1)[0]
        if (action === 'edit_motd') {
            YAHOO.util.Event.preventDefault(e);
            YAHOO.cereweb.motdDialog.content("", "");
            YAHOO.cereweb.motdDialog.show();
        }
    }
};

YAHOO.cereweb.getMotd = function(arg) {
    var callback = {
        success: function(o) {
            res = o.responseText;
            eval('var data = ' + res);
            YAHOO.cereweb.motdDialog.content(data.subject,
                data.message, arg);
            YAHOO.cereweb.motdDialog.show();
        },
        failure: function(o) {
            YAHOO.cereweb.motdDialog.content("", "");
        },
        timeout: 2000
    };
    var cObj = YAHOO.util.Connect.asyncRequest('POST',
        '/ajax/get_motd', callback, 'id=' + arg);
};

function initMotds() {
    YAHOO.util.Event.addListener(this, "click", editMotd);
};

function initActions() {
    YAHOO.util.Event.addListener(this, "click", actionClicked);
};



var initMotdDialog = function(e) {
    var myDiv = document.getElementById("editMotd");
    myDiv.style.display = 'none';
    YAHOO.cereweb.motdDialog = new YAHOO.widget.Dialog("editMotd", {
        'width': '500px',
        'height': '165px',
        'draggable': false,
        'visible': false,
        'fixedcenter': true,
        'postmethod': 'form' });
    var myButtons = [{
        text: 'Submit',
        handler: function(o) { YAHOO.cereweb.motdDialog.doSubmit(); },
        isDefault: true
    }];
    YAHOO.cereweb.motdDialog.cfg.queueProperty("buttons", myButtons);
    YAHOO.cereweb.motdDialog.setHeader("Edit Message");
    YAHOO.cereweb.motdDialog.render();
    YAHOO.cereweb.motdDialog.hide();
    myDiv.style.display = '';
    YAHOO.cereweb.motdDialog.content = function(subject, message, id) {
            document.getElementById('editMotdForm_id').value = id;
            document.getElementById('editMotdForm_subject').value = subject;
            document.getElementById('editMotdForm_message').value = message;
    };
};

YAHOO.util.Event.onAvailable('editMotd', initMotdDialog);
YAHOO.util.Event.onAvailable('motds', initMotds);
YAHOO.util.Event.onAvailable('actions', initActions);
