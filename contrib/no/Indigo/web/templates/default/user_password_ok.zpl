<span tal:define="title string:Nytt passord;title_id string:new_password" tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">

<p>
Passordet er nå byttet.
</p>
<span tal:condition="python: state['authlevel'] > 'c1'" tal:omit-tag="">

<p>
Du kan se eller skrive ut passord endret siden siste innlogging ved hjelp av menyen til venstre.
</p>
</span>

</span></span></span>
