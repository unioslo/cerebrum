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
    this.widget.dataReturnEvent.subscribe(this.dataReturn, this.input);
    this.widget.textboxKeyEvent.subscribe(this.textboxKey, this.input);
}
cereweb.ac_group.prototype = {
    /** Do the neccessary changes around the input element we want
     *  to add autocomplete to. */
    build: function() {
        var container = this.input.parentNode;
        this.dropdown = document.createElement('div');
        container.appendChild(this.dropdown);

        YD.addClass(this.dropdown, 'autocomplete');
        YD.addClass(container, 'autocomplete_container');
    },
    textboxKey: function(event, args, input) {
        input.style.backgroundColor = "";
    },
    dataReturn: function(event, args, input) {
        if (args[2].length === 0)
            input.style.backgroundColor = "red";
        else
            input.style.backgroundColor = "";
    },
    widgetOptions: {
        minQueryLength: 3
    },
    dataSourceOptions: {
        queryMatchCase: true,
        scriptQueryAppend: 'type=group'
    }
}

cereweb.ac_account = function(input) {
    cereweb.ac_account.superclass.constructor.call(this, input);
    this.widget.formatResult = this.formatResult;
}
YAHOO.extend(cereweb.ac_account, cereweb.ac_group);

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
    queryMatchCase: true
}

cereweb.ac_quicksearch = function(container) {
    var input = YD.get("ac_quicksearch");
    cereweb.ac_account.superclass.constructor.call(this, input);

    container.style.display = "";
    this.form = container.getElementsByTagName('form')[0];
    this.initForm();
}
YAHOO.extend(cereweb.ac_quicksearch, cereweb.ac_account);

cereweb.ac_quicksearch.prototype.initForm = function() {
    YE.addListener(this.form, 'submit', this.search, this, true);
}

cereweb.ac_quicksearch.prototype.dataReturn = function(event, args, input) {
    this.data = args[2];
}

cereweb.ac_quicksearch.prototype.search = function(e) {
    YE.preventDefault(e);
    var data = this.widget.data;
    if (!data) {
        this.widget.sendQuery(this.input.value);
        return;
    }

    if (data.length === 0) {
        this.input.style.backgroundColor = "red";
    } else {
        for (var i=0; i < data.length; i++) {
            if (data[i][0] === this.input.value) {
                var type = data[i][1].type;
                this.form.action = '/' + type + '/view';
                this.input.value = data[i][1].id;
                this.form.submit();
                return;
            }
        }
        this.input.focus();
        this.widget._populateList(this.input.value, data, this.widget);
    }
}

YE.onAvailable('quicksearch', function () {
        cereweb.quicksearch = new cereweb.ac_quicksearch(this);
    }
);

YE.addListener(window, 'load', initAutoComplete);
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

// Clears the searchform.
YAHOO.util.Event.addListener('search_clear', 'click', SR_clear);
function SR_clear(e) {
    YAHOO.util.Event.preventDefault(e);

    var form = document.getElementById('search_form');
    var base_uri = 'http://' + location.host;
    var uri = base_uri + "/entity/clear_search?url=" + form.action;
    
    //Resets all elements in the form.
    for(var i = 0; i < form.length; i++) {
        if (form.elements[i].type == "text") {
            form.elements[i].value = "";
        }
    }

    var callback = {
        success: remove_searchresult,
        failure: remove_searchresult,
        timeout: 5000
    }

    var cObj = YAHOO.util.Connect.asyncRequest('GET', uri, callback);
}

function remove_searchresult() {
    YAHOO.log('removing...');
    var maindiv = document.getElementById('content');
    if (YAHOO.util.Dom.inDocument('searchresult')) {
        var searchresult = document.getElementById('searchresult');
        var removed = maindiv.removeChild(searchresult);
    }
}

YAHOO.util.Event.addListener('search_submit', 'click', SR_submit);
function SR_submit(e) {
    return; // Disabled until pages are ready for DOM manipulation.
    YAHOO.util.Event.stopEvent(e); // AJAX takes over.
    var uri = 'http://' + location.host + '/ajax/search';
    
    var callback = {
        success: function(o) {
            var result = o.responseText;
            var maindiv = document.getElementById('content');
            remove_searchresult();

            maindiv.innerHTML = result + maindiv.innerHTML;
        },
        failure: function(o) {
            YAHOO.log('failure');
        },
        timeout: 5000
    }
    YAHOO.util.Connect.setForm('search_form');
    var cObj = YAHOO.util.Connect.asyncRequest('POST', uri, callback);
}
