<span tal:define="title string:Passord;title_id string:list_passwords" tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">

Passordet er skiftet.

<p>

<span tal:condition="python: state['authlevel'] > 'c1'" tal:omit-tag="">

Husk at du kan vise passord du har skiftet via menyen til venstre.

</span>

</span></span></span>
