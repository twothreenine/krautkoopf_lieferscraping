<!DOCTYPE html>
<div>
    <h3>{{option_name}}</h3>
    <p>{{description}}</p>
    <form action="/{{fc}}/{{configuration}}/display/{{run_name}}" method="post">
        <input name="method" value="{{option_name}}" hidden>
        {{!inputs}}
        <input type='submit' value={{option_name}}>
    </form>
</div>