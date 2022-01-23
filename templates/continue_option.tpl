<!DOCTYPE html>
<div>
    <h3>{{option_locales['name']}}</h3>
    <p>{{option_locales['description']}}</p>
    <form action="/{{fc}}/{{configuration}}/display/{{run_name}}" method="post" enctype="multipart/form-data">
        <input name="method" value="{{option_name}}" hidden>
        <p>{{!inputs}}</p>
        <input type='submit' value="{{option_locales['name']}}">
    </form>
</div>