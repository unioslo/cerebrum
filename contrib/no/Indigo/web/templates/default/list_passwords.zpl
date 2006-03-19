<span tal:define="title string:Nye passord;title_id string:list_passwords" tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">

<p>
Her finner du en oversikt over passord endret siden siste innlogging (bruk <i>Finn person</i> for å utføre passordskifte på brukere).
</p>

<span tal:condition="not:pwdlist" tal:omit-tag="">
<p>
  Ingen passord endret siden siste innlogging.
</p>
</span>

<span tal:condition="pwdlist" tal:omit-tag="">
  
  <table border="0">
    <tr><th>Brukernavn</th> <th>Passord</th><th></tr>
    <tr valign="top" tal:repeat="pwd pwdlist"
        tal:attributes="class python:test(path('repeat/pwd/odd'), 'white', 'grey')">
      <td><a tal:attributes="href string:?action=show_password_letter&username=${pwd/account_id}&pwd=${pwd/password}" tal:content="pwd/account_id"></a></td>
      <td tal:content="pwd/password"></td>
    </tr>
  </table>
</span>

  <p>
    <a href="?action=do_clear_passwords">Glem alle nye passord</a>
  </p>
  </span></span></span>
