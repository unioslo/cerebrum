<span tal:define="title string:Endre passord;title_id string:user_password" tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">
<form action="#" method="post">
<input type="HIDDEN" name="action" value="do_user_password">

  Nytt passord:<input type="password" name="newpass" size="12"><br>
  Gjennta nytt passord: <input type="password" name="newpass2" size="12"><br>
  <input type="SUBMIT" value="skift">
</form>
</span></span></span>
