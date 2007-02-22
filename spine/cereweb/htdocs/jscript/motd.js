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

cereweb.motd = {
    init: function() {
        var myDiv = document.getElementById("editMotd");
        myDiv.style.display = 'none';
        this.dialog = new YAHOO.widget.Dialog("editMotd", {
            'width': '500px',
            'height': '175px',
            'draggable': false,
            'visible': false,
            'fixedcenter': true,
            'postmethod': 'form' });
        var myButtons = [{
            text: 'Submit',
            handler: function(o) { this.dialog.doSubmit(); },
            isDefault: true
        }];
        this.dialog.cfg.queueProperty("buttons", myButtons);
        this.dialog.setHeader("Edit Message");
        this.dialog.render();
        this.dialog.hide();
        myDiv.style.display = '';
        this.dialog.content = function(subject, message, id) {
                document.getElementById('editMotdForm_id').value = id;
                document.getElementById('editMotdForm_subject').value = subject;
                document.getElementById('editMotdForm_message').value = message;
        }
        cereweb.action.add('edit_motd', this.edit, this);
    },
    edit: function(name, args) {
        var event = args[0];
        args = args[1];
        if (this.dialog) {
            YE.preventDefault(event);
            this.get(args.id);
        }
    },
    get: function(arg) {
        var callback = {
            success: function(o) {
                res = o.responseText;
                eval('var data = ' + res);
                this.dialog.content(data.subject,
                    data.message, arg);
                this.dialog.show();
            },
            failure: function(o) {
                this.dialog.content("", "");
            },
            timeout: 2000,
            scope: this
        };
        if (arg)
            var cObj = YC.asyncRequest('POST',
                '/ajax/get_motd', callback, 'id=' + arg);
        else {
            this.dialog.content("", "");
            this.dialog.show();
        }
    }
}
YE.onAvailable('editMotd', cereweb.motd.init, cereweb.motd, true);

if(cerebug) {
    log('motd is loaded');
}
