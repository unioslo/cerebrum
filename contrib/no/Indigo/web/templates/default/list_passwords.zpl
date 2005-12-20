<span tal:define="title string:Passord;title_id string:list_passwords" tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">

Passord satt siden du logget inn.  For å sette nytt passord på en
bruker må du først finne brukeren.  Du finner brukeren ved å søke på
personen som eier brukeren.

<span tal:condition="not:pwdlist" tal:omit-tag="">
<p>
  Du har ikke satt noen passord.
</span>

<span tal:condition="pwdlist" tal:omit-tag="">

  <table border="0">
    <tr><th>Brukernavn</th> <th>Passord</th></tr>
    <tr valign="top" tal:repeat="pwd pwdlist"
        tal:attributes="class python:test(path('repeat/pwd/odd'), 'white', 'grey')">
      <td><a tal:attributes="href string:?action=show_password_mail&username=${pwd/account_id}" tal:content="pwd/account_id"></a></td> <!-- account_id is really a uname.  Blame bofhd_uio_cmds -->
      <td tal:content="pwd/password"></td>
    </tr>
  </table>
</span>

<p>
  <a href="?action=do_clear_passwords">Glem</a> alle passord
  </p>
  
  </span></span></span>
