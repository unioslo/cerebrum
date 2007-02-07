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

YAHOO.util.Event.addListener('search_clear', 'click', SR_clear);
YAHOO.util.Event.addListener('search_submit', 'click', SR_submit);

/** AutoCompleter object. */
cereweb.ac = {
    /* DataSource for accounts and person names. */
    account: {
        dataSource: new YAHOO.widget.DS_XHR(
            '/ajax/search',
            ["ResultSet", "name"],
            { queryMatchCase: true }
        ),
        formatResult: function(aResultItem, sQuery) {
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
    },
    group: {
        dataSource: new YAHOO.widget.DS_XHR(
            '/ajax/search',
            ["ResultSet", "name"],
            {
                queryMatchCase: true,
                scriptQueryAppend: 'type=group'
            }
        )
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
    dataSource: new YAHOO.widget.DS_JSArray(
            ['config must specify a datasource']
        ),
    config: { minQueryLength: 3 },
    factory: function(input, config) {
        var container = input.parentNode;
        var acdiv = document.createElement('div');
        YD.addClass(acdiv, 'autocomplete');
        container.appendChild(acdiv);
        YD.addClass(container, 'autocomplete_container');

        config.dataSource = config.dataSource || cereweb.ac.dataSource;
        config.config = config.config || cereweb.ac.config;
        config.dataReturn = config.dataReturn || cereweb.ac.dataReturn;
        config.textboxKey = config.textboxKey || cereweb.ac.textboxKey;

        var myac = new YAHOO.widget.AutoComplete (input, acdiv, config.dataSource, config.config);
        myac.dataReturnEvent.subscribe(config.dataReturn, input);
        myac.textboxKeyEvent.subscribe(config.textboxKey, input);

        if (config.formatResult)
            myac.formatResult = config.formatResult;
        return myac;
    }
}

cereweb.quicksearch = {
    init: function() {
        this.style.display = "";
        var input = YD.get("ac_quicksearch");
        cereweb.quicksearch.input = input;
        cereweb.quicksearch.initForm(this.getElementsByTagName('form')[0]);
        config = cereweb.ac.account;
        config.dataReturn = function(event, args, input) {
            cereweb.quicksearch.data = args[2];
        }
        cereweb.quicksearch.ac = cereweb.ac.factory(input, config);
    },
    initForm: function(form) {
        cereweb.quicksearch.form = form;
        YE.addListener(form, 'submit', cereweb.quicksearch.search);
    },
    search: function(e) {
        YE.preventDefault(e);
        var input = cereweb.quicksearch.input;
        var data = cereweb.quicksearch.data;

        if (!data) {
            cereweb.quicksearch.ac.sendQuery(input.value);
        }

        if (data.length === 0) {
            input.style.backgroundColor = "red";
        } else {
            for (var i=0;i<data.length;i++) {
                if (data[i][0] === input.value) {
                    var form = cereweb.quicksearch.form;
                    var type = data[i][1].type;
                    form.action = '/' + type + '/view';
                    input.value = data[i][1].id;
                    form.submit();
                }
            }
            input.focus();
            cereweb.quicksearch.ac._populateList(input.value, cereweb.quicksearch.data,
                cereweb.quicksearch.ac);
        }
    }
}
YE.onAvailable('quicksearch', cereweb.quicksearch.init);

YE.addListener(window, 'load', initAutoComplete);
function initAutoComplete(event) {

    var account_completers = YD.getElementsByClassName('ac_account', 'input');
    var group_completers = YD.getElementsByClassName('ac_group', 'input');
    if (account_completers.length > 0)
        YD.batch(account_completers, cereweb.ac.factory, cereweb.ac.account);
    if (group_completers.length > 0)
        YD.batch(group_completers, cereweb.ac.factory, cereweb.ac.group);
}

// Clears the searchform.
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
