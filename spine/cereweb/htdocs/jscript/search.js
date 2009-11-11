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
    cereweb.events.sessionError.subscribe(this.handleSessionError, this, true);

    this.widget.doBeforeExpandContainer = this.doBeforeExpandContainer;
    if (this.input.value)
        this.widget.sendQuery(this.input.value);
}
cereweb.ac_group.prototype = {
    /** Do the neccessary changes around the input element we want
     *  to add autocomplete to. */
    build: function() {
        this.selected_id = document.createElement('input');
        this.selected_id.type = "hidden";
        this.selected_id.name = "selected_id";
        this.dropdown = document.createElement('div');
        var container = this.input.parentNode;
        if (YD.hasClass(container, 'required'))
            this.valid = false;
        else
            this.valid = true;
        container.appendChild(this.dropdown);
        container.appendChild(this.selected_id);
        this.form = container;
        while (this.form.tagName.toLowerCase() !== 'form')
            this.form = this.form.parentNode;

        YD.addClass(this.dropdown, 'autocomplete');
        YD.addClass(container, 'autocomplete_container');
    },
    handleSessionError: function() {
        this.disable();
        this.input.value = "Session error.";
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
        this.selected_id.value = "";
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
        var obj = data[1];
        this.selected_id.value = obj.id;
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
    YD.get("tabview").innerHTML += '\
            <div id="quicksearch"> \
                <form id="qs_form"> \
                    <div id="qs_dform" class="required"> \
                        <input name="id" type="hidden" /> \
                        <label id="qs_query_label" for="qs_query">Search</label> \
                        <input id="qs_query" name="query" type="text" /> \
                        <img id="qs_qmark" alt="Help" src="/img/q.gif" />  \
                    </div> \
                    <div class="optional"> \
                        <input id="qs_submit" type="submit" value="Search" /> \
                    </div> \
                </form> \
            </div>';
    this.qs = YD.get("quicksearch");
    this.form = YD.get("qs_form");
    this.id = this.form['id'];
    this.input = YD.get("qs_query");
    this.label = YD.get("qs_query_label");
    this.qs_submit = YD.get("qs_submit");
    this.initTooltip("qs_qmark");

    cereweb.ac_quicksearch.superclass.constructor.call(this, this.input);
    this.widget.itemSelectEvent.subscribe(this.itemSelect, this, true);

    container.style.display = "";
    YE.addListener(this.input, 'focus', this.openSearch, this, true);
    YE.addListener(this.input, 'blur', this.closeSearch, this, true);
    YE.addListener(this.qs_submit, 'click', this.submitClicked, this, true);

    this.updateLabel("close");
}
YAHOO.lang.extend(cereweb.ac_quicksearch, cereweb.ac_account);

cereweb.ac_quicksearch.prototype.initTooltip = function(el) {
    new YAHOO.widget.Tooltip("tt1", {context: el, text: '\
                        <ul class="help"> \
                            <li>Search for accounts by using only small letters or by prepending the search text with <em>a:</em></li> \
                            <li>Search for people by writing the first character in uppercase or by prepending the search text with <em>p:</em></li> \
                            <li>Search for groups by prepending the search text with <em>g:</em></li> \
                        </ul>'});
}

cereweb.ac_quicksearch.prototype.submitClicked = function(e) {
    if (this.valid) {
        return true;
    }
    e.preventDefault();
    clearTimeout(this.closeTimer);
    this.input.focus();
    this.widget.sendQuery(this.input.value);
}

cereweb.ac_quicksearch.prototype.openSearch = function(args) {
    if (this.closeTimer >= 0) {
        clearTimeout(this.closeTimer);
        this.closeTimer = -1;
    }

    YD.addClass(this.qs, "open");
    this.updateLabel("open");
}

cereweb.ac_quicksearch.prototype.closeSearch = function(args) {
    var self = this;
    this.closeTimer = setTimeout(function() {
        YD.removeClass(self.qs, "open");
        self.updateLabel("close");
        self.closeTimer = -1;
    }, 500);
}

cereweb.ac_quicksearch.prototype.updateLabel = function(state) {
    if (state === "close" && this.input.value !== '')
        this.label.style.textIndent = '-10000px';
    else
        this.label.style.textIndent = '0px';
}


cereweb.ac_quicksearch.prototype.handleSessionError = function() {
    this.disable();
    this.input.value = "Session error.";
    this.label.style.textIndent = '-10000px';
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
    if (!data)
        var data = this.data[0][1];
    else
        var data = data[1];

    var type = data.type;
    this.form.action = '/' + type + '/view';
    this.id.value = data.id;
    this.valid = true;
}

cereweb.ac_quicksearch.prototype.dataSourceOptions = {
    queryMatchCase: true
}

YE.onContentReady('container', function () {
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
YE.onContentReady('content', cereweb.autocomplete.init);

if(cereweb.debug) {
    log('search is loaded');
}
