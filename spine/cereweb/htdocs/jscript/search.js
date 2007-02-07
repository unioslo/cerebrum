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
    account_DS: new YAHOO.widget.DS_XHR(
        '/ajax/search',
        ["ResultSet", "name", "owner.name"],
        { queryMatchCase: true }
    ),
    group_DS: new YAHOO.widget.DS_XHR(
        '/ajax/search',
        ["ResultSet", "name", "owner.name"],
        {
            queryMatchCase: true,
            scriptQueryAppend: 'type=group'
        }
    ),
    formatResult: function(aResultItem, sQuery) {
        var name = aResultItem[0];
        var owner = aResultItem[1];
        var aMarkup = ["<div id='ysearchresult'>",
            '<div style="float:left;width:6em;">',
            name,
            '</div>',
            owner,
            "</div>"];
        return (aMarkup.join(""));
    },
    dataReturn: function(event, args, input) {
        if (args[2].length === 0)
            input.style.backgroundColor = "red";
        else
            input.style.backgroundColor = "";
    },
    textboxKey: function(event, args, input) {
        input.style.backgroundColor = "";
    },
    factory: function(input, type) {
        var container = input.parentNode;
        var acdiv = document.createElement('div');
        acdiv.setAttribute('id', 'autocomplete_' + input.id);
        container.appendChild(acdiv);
        YD.addClass(container, 'autocomplete_container');
        var DS;
        if (type === 'account')
            DS = cereweb.ac.account_DS;
        else if (type === 'group')
            DS = cereweb.ac.group_DS;
        else DS = new YAHOO.widget.DS_JSArray(['autocomplete not implemented for type ' + type]);

        var myac = new YAHOO.widget.AutoComplete
            (input, acdiv, DS);
        myac.minQueryLength = 3;
        myac.dataReturnEvent.subscribe(
            cereweb.ac.dataReturn, input);
        myac.textboxKeyEvent.subscribe(
            cereweb.ac.textboxKey, input);
        if (type === 'account')
            myac.formatResult = cereweb.ac.formatResult;
        return myac;
    }
}

YE.addListener(window, 'load', initAutoComplete);
function initAutoComplete(event) {
    var account_completers = YD.getElementsByClassName('ac_account', 'input');
    var group_completers = YD.getElementsByClassName('ac_group', 'input');
    YD.batch(account_completers, cereweb.ac.factory, 'account');
    YD.batch(group_completers, cereweb.ac.factory, 'group');
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
