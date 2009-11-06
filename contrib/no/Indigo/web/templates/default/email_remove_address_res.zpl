<span tal:define="title string:E-postalias fjernet;title_id string:email_remove_address_res" 
      tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">

<p>
E-postalias: <span tal:content="address">adresse</span> for brukeren <span tal:content="username">brukernavn</span> er nå fjernet.
</p>

</span></span></span>
