<span tal:define="title string:Bytte passord;title_id string:user_password" tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">
<form action="#" method="post">
<input type="HIDDEN" name="action" value="do_user_password">
  
<table border=0>
  <tr><td>Nytt passord:</td><td><input type="password" name="newpass" size="12"></td></tr>
  <tr><td>Bekreft nytt passord:</td><td><input type="password" name="newpass2" size="12"></td></tr>
  <tr><td colspan=2></td></tr>
  <tr><td colspan=2><input type="SUBMIT" value="Bytt passord"></td></tr>
</table>
</form>
</span></span></span>
