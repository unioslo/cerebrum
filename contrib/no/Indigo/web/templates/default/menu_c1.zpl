Logget inn som:<br>
<span tal:content="state/authuser_str" tal:omit-tag="">useradm</span> [<a href="?action=do_logout">Logg ut</a>]
<br>
(<a href="?action=set_style&val=default,c1">Elev</a>, <a href="?action=set_style&val=ofk,c2">Lita</a>, <a href="?action=set_style&val=default,c3">Super</a>)

<hr>
<dl>
  <dt>Elev meny
  <dd>
    <a tal:attributes="href string:?action=show_person_info">Om meg</a><br>
    <a tal:attributes="href string:?action=show_user_password">Passord skifte</a><br>
</dl>
