<!DOCTYPE html>
<html>
    <head>
        <title>{{foodcoop}} Lieferscraping - {{supplier}} - {{run}}</title>
        <link rel="stylesheet" href="/templates/styles.css" type="text/css">
    </head>

    <body>
        <div>
            <form action="/{{fc}}"><input type='submit' value='Zurück zum Hauptmenü'></form>
            <p>{{messages}}</p>
            <form action="/{{fc}}/{{supplier}}"><input type='submit' value='Zurück zu {{supplier}}'></form>
            <h1>{{supplier}} - Ausführung {{run}}</h1>
            {{!downloads}}
            {{!content}}
        </div>
    </body>
</html>