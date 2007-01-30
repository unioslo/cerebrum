function editMotd(e) {
    var t = YAHOO.util.Event.getTarget(e);
    var content = t.innerText || t.textContent;
    if (t.nodeName.toLowerCase() === 'a' &&
         content === 'edit') {
            var argument = t.href.replace(/.*?id=/,'');
            YAHOO.util.Event.preventDefault(e);
            YAHOO.cereweb.getMotd(argument);
    }
}

YAHOO.cereweb.getMotd = function(arg) {
    var callback = {
        success: function(o) {
            res = o.responseText;
            eval('var data = ' + res);
            idInput = document.getElementById('editMotdForm_id');
            subjectInput = document.getElementById('editMotdForm_subject');
            messageInput = document.getElementById('editMotdForm_message');

            subjectInput.value = data.subject;
            messageInput.value = data.message;
            idInput.value = arg;
            YAHOO.cereweb.motdDialog.show();
        },
        failure: function(o) {
            YAHOO.cereweb.motdDialog.subject.value = "";
            YAHOO.cereweb.motdDialog.message.value = "";
        },
        timeout: 2000
    };
    var cObj = YAHOO.util.Connect.asyncRequest('POST',
        '/ajax/get_motd', callback, 'id=' + arg);
};

function initMotds() {
    YAHOO.util.Event.addListener(this, "click", editMotd);
}

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
};

YAHOO.util.Event.onAvailable('editMotd', initMotdDialog);
YAHOO.util.Event.onAvailable('motds', initMotds);
