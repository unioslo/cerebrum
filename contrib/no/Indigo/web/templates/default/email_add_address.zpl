<span tal:define="title string:Nytt e-postalias;title_id string:email_add_address_res" 
      tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">

<div tal:condition="message" tal:content="message">Melding</div>

<form action="#" method="post">
<input type="hidden" name="action" value="do_email_add_address">
<input type="hidden" name="username" tal:attributes="value string:${username}">

<table border="0">
    <span tal:repeat="address email_addresses" tal:omit-tag="">
    <tr>
        <td></td>
        <td tal:content="address">address</td>
    </tr>
    </span>

    <tr></tr>

    <tr>
        <td>Nytt alias:</td>
        <td><input type="text" name="new_address" size="50">
            <input type="submit" value="Legg til"></td>
    </tr>

<table>
</form>


</span></span></span>
