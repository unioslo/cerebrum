<span tal:define="title string:Brukernavn;title_id string:user_find_res" 
      tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">

<span tal:condition="not:userlist" tal:omit-tag="">
Ingen brukernavn oppfyller dine søkekriterier.
</span>

<span tal:condition="userlist" tal:omit-tag="">
  <table border="1">
    <tr><th>Brukernavn</th></tr>
    <tr valign="top" tal:repeat="user userlist"
        tal:attributes="class python:test(path('repeat/user/odd'), 'white', 'grey')">
      <td><a tal:attributes="href string:?action=show_person_info&entity_id=${user/owner_id}" 
             tal:content="user/username">testbruker</a></td>   
    </tr>
  </table>
</span>
</span></span></span>
