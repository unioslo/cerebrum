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
cereweb.ac_group = function(input) {
    this.input = input;
    this.build();
    this.initForm();
    this.dataSource = new YAHOO.widget.DS_XHR(
        '/ajax/search',
        ["ResultSet", "name"],
        this.dataSourceOptions
    );

    this.widget = new YAHOO.widget.AutoComplete(
        this.input,
        this.dropdown,
        this.dataSource,
        this.widgetOptions
    );

    this.widget.dataRequestEvent.subscribe(this.dataRequest, this, true);
    this.widget.dataReturnEvent.subscribe(this.dataReturn, this, true);
    this.widget.dataErrorEvent.subscribe(this.dataError, this, true);
    this.widget.textboxKeyEvent.subscribe(this.textboxKey, this, true);

    this.widget.doBeforeExpandContainer = this.doBeforeExpandContainer;
    if (this.input.value)
        this.widget.sendQuery(this.input.value);
}
cereweb.ac_group.prototype = {
    /** Do the neccessary changes around the input element we want
     *  to add autocomplete to. */
    build: function() {
        this.dropdown = document.createElement('div');
        var container = this.input.parentNode;
        container.appendChild(this.dropdown);
        this.form = container;
        while (this.form.tagName.toLowerCase() !== 'form')
            this.form = this.form.parentNode;

        YD.addClass(this.dropdown, 'autocomplete');
        YD.addClass(container, 'autocomplete_container');
    },
    initForm: function() {
        YE.addListener(this.form, 'submit', this.submit, this, true);
    },
    textboxKey: function(event, args) {
        this.input.style.backgroundColor = "";
    },
    dataRequest: function(event, args) {
        this.input.style.backgroundColor = "blue";
    },
    dataError: function(event, args) {
        this.input.style.backgroundColor = "red";
    },
    dataReturn: function(event, args) {
        var query = unescape(args[1]);
        while(query.length > 0 && query.charAt(0) === ' ')
            query = query.slice(1);
        this.data = args[2];

        if (this.data.length === 0 && query.length >= 3)
            this.dataError();
        else
            this.input.style.backgroundColor = "";

        this.valid = false;
        if (this.data.length === 1)
            this.parseData();

        if (this.widget.submitting) {
            this.widget.submitting = false;
            this.submit();
        }
    },
    parseData: function() {
        this.valid = true;
    },
    widgetOptions: {
        minQueryLength: 3
    },
    dataSourceOptions: {
        queryMatchCase: true,
        scriptQueryAppend: 'type=group'
    },
    submit: function(e) {
        if (e) {
            YE.preventDefault(e);
            this.widget.submitting = true;
        }

        if (this.valid) {
            this.widget.submitted = true;
            this.form.submit();
        } else 
            this.widget.sendQuery(this.input.value);
    },
    doBeforeExpandContainer: function(oTextBox, oContainer, sQuery, aResults) {
        if (this.submitted || this.submitting)
            return false;
        else return true;
    }
}

cereweb.ac_account = function(input) {
    cereweb.ac_account.superclass.constructor.call(this, input);
    this.widget.formatResult = this.formatResult;
}
YAHOO.lang.extend(cereweb.ac_account, cereweb.ac_group);

cereweb.ac_account.prototype.formatResult = function(aResultItem, sQuery) {
    var name = aResultItem[0];
    var owner = aResultItem[1].owner;
    var aMarkup = ["<div id='ysearchresult'>",
        '<div style="float:left;width:6em;">',
        name,
        '</div>',
        owner.name,
        "</div>"];
    return (aMarkup.join(""));
}

cereweb.ac_account.prototype.dataSourceOptions = {
    queryMatchCase: true,
    scriptQueryAppend: 'output=account'
}

cereweb.ac_quicksearch = function(container) {
    var qdiv = cereweb.createDiv('quicksearch', 'tabview');
    this.form = document.createElement('form');
    this.form.setAttribute('id', 'qs_form');
    qdiv.appendChild(this.form);
    var dForm = cereweb.createDiv('qs_dform', 'qs_form');

    this.input = document.createElement('input');
    this.label = document.createElement('label');
    this.id = document.createElement('input');
    this.input.setAttribute('name', 'query');
    this.input.setAttribute('type', 'text'),
    this.label.setAttribute('for', 'query');
    this.id.setAttribute('name', 'id');
    this.id.setAttribute('type', 'hidden');
    
    dForm.appendChild(this.id);
    dForm.appendChild(this.label);
    dForm.appendChild(this.input);


    cereweb.ac_quicksearch.superclass.constructor.call(this, this.input);

    this.widget.itemSelectEvent.subscribe(this.itemSelect, this, true);
    container.style.display = "";
    this.updateLabel();
    YE.addListener(this.input, 'focus', this.updateLabel, this, true);
    YE.addListener(this.input, 'blur', this.updateLabel, this, true);
}
YAHOO.lang.extend(cereweb.ac_quicksearch, cereweb.ac_account);

cereweb.ac_quicksearch.prototype.updateLabel = function(args) {
    if (args && args.type === 'focus')
        this.label.style.textIndent = '-1000px';
    else if (this.input.value !== '')
        this.label.style.textIndent = '-1000px';
    else
        this.label.style.textIndent = '0px';
}

cereweb.ac_quicksearch.prototype.formatResult = function(aResultItem, sQuery) {
    var type = aResultItem[1].type;
    var name = aResultItem[1].name;
    var aMarkup = ["<div id='ysearchresult'>",
        '<div style="float:left;width:6em;">',
        type,
        '</div>',
        name,
        "</div>"];
    return (aMarkup.join(""));
}

cereweb.ac_quicksearch.prototype.dataReturn = function(event, args) {
    var query = unescape(args[1]);
    var i = query.search(':');
    query = query.slice(i + 1);
    while(query.length > 0 && query.charAt(0) === ' ')
        query = query.slice(1);
    this.data = args[2];
    if (this.data.length === 0 && query.length >= 3)
        this.dataError();
    else
        this.input.style.backgroundColor = "";

    this.valid = false;
    if (this.data.length === 1)
        this.parseData();

    if (this.widget.submitting) {
        this.widget.submitting = false;
        this.submit();
    }
}
cereweb.ac_quicksearch.prototype.itemSelect = function(event, args) {
    var data = args[2][1];
    var prefix;
    switch (data.type) {
        case 'account':
            prefix = 'a: ';
            break;
        case 'person':
            prefix = 'p: ';
            break;
        case 'group':
            prefix = 'g: ';
            break;
    }
    this.input.value = prefix + data.name;
}

cereweb.ac_quicksearch.prototype.parseData = function() {
    this.valid = true;

    var type = this.data[0][1].type;
    this.form.action = '/' + type + '/view';
    this.id.value = this.data[0][1].id;
}

cereweb.ac_quicksearch.prototype.dataSourceOptions = {
    queryMatchCase: true
}

YE.onAvailable('container', function () {
        cereweb.quicksearch = new cereweb.ac_quicksearch(this);
    }
);

YE.onAvailable('content', initAutoComplete);
function initAutoComplete(event) {
    var account_completers = YD.getElementsByClassName('ac_account', 'input');
    var group_completers = YD.getElementsByClassName('ac_group', 'input');
    if (account_completers.length > 0)
        YD.batch(account_completers, function(input) {
            new cereweb.ac_account(input);
        });
    if (group_completers.length > 0)
        YD.batch(group_completers, function (input) {
            new cereweb.ac_group(input);
        });
}

cereweb.search = {
    callback:  {
        success: function(o) {
            cereweb.search.clear_messages();
            var result = o.responseText;
            cereweb.search.show_results(result);
        },
        failure: function(o) {
            cereweb.search.clear_messages();
            var messages = eval('(' + o.responseText + ')');
            cereweb.search.add_messages(messages);
        }
    },
    submit: function(e) {
        YE.stopEvent(e); // AJAX takes over.
        var form = YD.get('search_form');
        YC.setForm(form);

        var cObj = YC.asyncRequest('POST', form.action,
            cereweb.search.callback);
    },
    show_results: function(res) {
        var old = YD.get('content');
        var parent = old.parentNode;
        cereweb.search.content = old;
        var content = document.createElement('div');
        content.setAttribute('id', 'content');
        content.innerHTML = res;
        parent.replaceChild(content, old);
        var backLinkDiv = document.createElement('div');
        var backLink = document.createElement('a');
        backLink.innerHTML = 'Back';
        backLink.href = '#';
        backLinkDiv.appendChild(backLink);
        content.appendChild(backLinkDiv);
        YE.addListener(backLink, 'click', cereweb.search.show_form);
    },
    add_messages: function(messages) {
        var messages = messages.messages;
        var div = YD.get('messages');
        for (var i=0; i<messages.length; i++) {
            var message = document.createElement('span');
            if (messages[i][1])
                message.setAttribute('class', 'error');
            message.innerHTML = messages[i][0];
            div.appendChild(message);
            div.appendChild(document.createElement('br'));
        }
    },
    clear_messages: function() {
        var div = YD.get('messages');
        div.innerHTML = "";
    },
    show_form: function() {
        var content = YD.get('content');
        var parent = content.parentNode;
        parent.replaceChild(cereweb.search.content, content);
    },
    clear_search: function() {
        var callback = { success: function(o) {}, failure: function(o) {} }
        var form = YD.get('search_form');
        var url = '/entity/clear_search';
        var arg = 'url=' + form.action;
        var cObj = YC.asyncRequest('POST', url, callback, arg);
        document.location = document.location; // Get rid of the pesky form values.
    }
}
YE.addListener('search_form', 'submit', cereweb.search.submit);
YE.addListener('search_clear', 'click', cereweb.search.clear_search);

if(cerebug) {
    log('search is loaded');
}
