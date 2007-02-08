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

    this.widget.dataReturnEvent.subscribe(this.dataReturn, this, true);
    this.widget.textboxKeyEvent.subscribe(this.textboxKey, this, true);

    this.widget.doBeforeExpandContainer = this.doBeforeExpandContainer(this);
    if (this.input.value)
        this.widget.sendQuery(this.input.value);
}
cereweb.ac_group.prototype = {
    /** Do the neccessary changes around the input element we want
     *  to add autocomplete to. */
    build: function() {
        this.dropdown = document.createElement('div');
        container = this.input.parentNode;
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
    dataReturn: function(event, args) {
        this.data = args[2];
        if (this.data.length === 0)
            this.input.style.backgroundColor = "red";
        else {
            this.input.style.backgroundColor = "";
        }

        if (this.submit_on_hit && this.data.length === 1)
            this.form.submit(); // FIXME: This should really trigger the submit event.
    },
    widgetOptions: {
        // forceSelection: true, // FIXME: Is this option able to help simplify the code?
        minQueryLength: 3
    },
    dataSourceOptions: {
        queryMatchCase: true,
        scriptQueryAppend: 'type=group'
    },
    submit: function(e) {
        YE.preventDefault(e);
        this.submitted = true;

        var data = this.data;
        if (!data) {
            this.widget.sendQuery(this.input.value);
            this.submit_on_hit = true;
        } else if (data.length === 0) {
            this.input.style.backgroundColor = "red";
        } else {
            this.input.style.backgroundColor = "";
            for (var i=0; i < data.length; i++) {
                if (data[i][0] === this.input.value) {
                    this.form.submit();
                    return;
                }
            }
            this.input.focus();
            this.widget._populateList(this.input.value, data, this.widget);
        }
        this.submitted = false;
    },
    doBeforeExpandContainer: function(closure) { // FIXME: Check for memory leaks.
        return function(oResultItem, sQuery) {
            var expand = this.submitted && false || true;
            var hit = closure.data && closure.data.length === 1 && 
                            closure.data[0][0] === closure.input.value;
            expand = expand && !hit;
            return expand;
        }
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
    var input = YD.get("ac_quicksearch_name");
    this.id = YD.get("ac_quicksearch_id");
    cereweb.ac_quicksearch.superclass.constructor.call(this, input);
    container.style.display = "";
}
YAHOO.extend(cereweb.ac_quicksearch, cereweb.ac_account);

cereweb.ac_quicksearch.prototype.dataReturn = function(event, args) {
    this.data = args[2];
    var type;
    if (this.data.length === 1) {
        type = this.data[0][1].type;
        this.id.value = this.data[0][1].id;
        log(this.data[0][0] + ' === ' + this.input.value + '?');
        this.input.value = this.data[0][0]; // FIXME: What does this really do?
    } else {
        for (var i=0; i < this.data.length; i++) {
            if (this.data[i][0] === this.input.value) {
                type = this.data[i][1].type;
                this.id.value = this.data[i][1].id;
            }
        }
    }
    if(type)
        this.form.action = '/' + type + '/view';

    cereweb.ac_quicksearch.superclass.dataReturn.call(this, event, args);
}

YE.onAvailable('ac_quicksearch', function () {
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
