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

cereweb.actions['edit_motd'] = function(event, args) {
    if (cereweb.motdDialog) {
        YE.preventDefault(event);
        cereweb.getMotd(args['id']);
    }
}

cereweb.getMotd = function(arg) {
    var callback = {
        success: function(o) {
            res = o.responseText;
            eval('var data = ' + res);
            cereweb.motdDialog.content(data.subject,
                data.message, arg);
            cereweb.motdDialog.show();
        },
        failure: function(o) {
            cereweb.motdDialog.content("", "");
        },
        timeout: 2000
    };
    if (arg)
        var cObj = YC.asyncRequest('POST',
            '/ajax/get_motd', callback, 'id=' + arg);
    else {
        cereweb.motdDialog.content("", "");
        cereweb.motdDialog.show();
    }
};

var initMotdDialog = function(e) {
    var myDiv = document.getElementById("editMotd");
    myDiv.style.display = 'none';
    cereweb.motdDialog = new YAHOO.widget.Dialog("editMotd", {
        'width': '500px',
        'height': '165px',
        'draggable': false,
        'visible': false,
        'fixedcenter': true,
        'postmethod': 'form' });
    var myButtons = [{
        text: 'Submit',
        handler: function(o) { cereweb.motdDialog.doSubmit(); },
        isDefault: true
    }];
    cereweb.motdDialog.cfg.queueProperty("buttons", myButtons);
    cereweb.motdDialog.setHeader("Edit Message");
    cereweb.motdDialog.render();
    cereweb.motdDialog.hide();
    myDiv.style.display = '';
    cereweb.motdDialog.content = function(subject, message, id) {
            document.getElementById('editMotdForm_id').value = id;
            document.getElementById('editMotdForm_subject').value = subject;
            document.getElementById('editMotdForm_message').value = message;
    };
};

YE.onAvailable('editMotd', initMotdDialog);
