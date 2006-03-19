<span tal:define="title string:Brukere;title_id string:user_find_res" tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">
<!--Foreløpig ikke i bruk-->
<span tal:condition="not:userlist" tal:omit-tag="">
 Ingen brukere oppfylte dine søkekriterier.
</span>

<span tal:condition="userlist" tal:omit-tag="">
Klikk på brukernavn for å velge bruker.

  <table border="1">
    <tr><th>Brukernavn</th> <th>Sluttdato</th> <th>Primær tilknytning</th> <th>Brukergruppe</th></tr>
    <tr valign="top" tal:repeat="user userlist"
        tal:attributes="class python:test(path('repeat/user/odd'), 'white', 'grey')">
      <td><a tal:attributes="href string:?action=do_select_target&type=account&entity_id=${user/entity_id}" tal:content="user/username">foo\
user</a></td>
      <td tal:content="user/expire">2001-01-02</td>
      <td>Student ved Matnant (150000)</td>
      <td>hjemmeområde bruker</td> <!-- ldap, mail, windows, hjemmeområde -->
    </tr>
  </table>
</span>

</span></span></span>
