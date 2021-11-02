<!DOCTYPE html>
<html>
    <head>
        <title>{{foodcoop}} Lieferscraping - {{configuration}} - {{run}}</title>
        <link rel="stylesheet" href="/templates/styles.css" type="text/css">
    </head>

    <body>
        <div>
            <form action="/{{fc}}"><input type='submit' value='Zurück zum Hauptmenü'></form>
            <p>{{messages}}</p>
            <form action="/{{fc}}/{{configuration}}"><input type='submit' value='Zurück zu {{configuration}}'></form>
            <h1>{{configuration}} - Ausführung {{run}}</h1>
            {{!downloads}}
            {{!content}}
        </div>
    </body>
</html>