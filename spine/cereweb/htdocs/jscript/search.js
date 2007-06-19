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
    this.widget.itemSelectEvent.subscribe(this.dataSelect, this, true);
    this.widget.textboxKeyEvent.subscribe(this.textboxKey, this, true);
    cereweb.events.sessionError.subscribe(this.disable, this, true);

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
        if (YD.hasClass(container, 'required'))
            this.valid = false;
        else
            this.valid = true;
        container.appendChild(this.dropdown);
        this.form = container;
        while (this.form.tagName.toLowerCase() !== 'form')
            this.form = this.form.parentNode;

        YD.addClass(this.dropdown, 'autocomplete');
        YD.addClass(container, 'autocomplete_container');
    },
    disable: function() {
        this.input.disabled = true;
    },
    initForm: function() {
        YD.addClass(this.form, 'ac');
        YE.addListener(this.form, 'submit', this.submit, this, true);
    },
    textboxKey: function(event, args) {
        this.input.style.backgroundColor = "";
    },
    dataRequest: function(event, args) {
        cereweb.ajax.begin();
    },
    dataError: function(event, args) {
        cereweb.ajax.done();
        this.input.style.backgroundColor = "red";
    },
    dataReturn: function(event, args) {
        cereweb.ajax.done();
        var query = unescape(args[1]);
        while(query.length > 0 && query.charAt(0) === ' ')
            query = query.slice(1);
        this.data = args[2];

        if (this.data.length === 0 && query.length >= 3)
            this.dataError();
        else
            this.input.style.backgroundColor = "";

        if (this.data.length === 1)
            this.parseData();

        if (this.widget.submitting) {
            this.widget.submitting = false;
            this.submit();
        }
    },
    dataSelect: function(event, args) {
        this.valid = false;
        this.parseData(args[2]);
    },
    parseData: function(data) {
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
    YD.addClass(dForm, 'required');


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
    cereweb.ajax.done();
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

cereweb.ac_quicksearch.prototype.parseData = function(data) {
    this.valid = true;
    if (!data)
        var data = this.data[0][1];
    else
        var data = data[1];

    var type = data.type;
    this.form.action = '/' + type + '/view';
    this.id.value = data.id;
}

cereweb.ac_quicksearch.prototype.dataSourceOptions = {
    queryMatchCase: true
}

YE.onAvailable('container', function () {
        cereweb.quicksearch = new cereweb.ac_quicksearch(this);
    }
);

cereweb.autocomplete = {
    init: function (event) {
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
}
YE.onAvailable('content', cereweb.autocomplete.init);

if(cereweb.debug) {
    log('search is loaded');
}
