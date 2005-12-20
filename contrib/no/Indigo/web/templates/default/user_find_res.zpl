<span tal:define="title string:User find res;title_id string:user_find_res" tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">

<span tal:condition="not:userlist" tal:omit-tag="">
  No matches
</span>

<span tal:condition="userlist" tal:omit-tag="">
  Click user to select as new user target.

  <table border="1">
    <tr><th>Uname</th> <th>Expire-date</th> <th>Primær affiliation</th> <th>kategori</th></tr>
    <tr valign="top" tal:repeat="user userlist"
        tal:attributes="class python:test(path('repeat/user/odd'), 'white', 'grey')">
      <td><a tal:attributes="href string:?action=do_select_target&type=account&entity_id=${user/entity_id}" tal:content="user/username">foouser</a></td>
      <td tal:content="user/expire">2001-01-02</td>
      <td>Student ved Matnant (150000)</td>
      <td>hjemmeområde bruker</td> <!-- ldap, mail, windows, hjemmeområde -->
    </tr>
  </table>
</span>

</span></span></span>
