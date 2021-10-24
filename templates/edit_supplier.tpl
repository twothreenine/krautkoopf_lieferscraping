<!DOCTYPE html>
<html>
    <head>
        <title>{{foodcoop}} Lieferscraping - {{supplier}}</title>
        <link rel="stylesheet" href="/templates/styles.css" type="text/css">
    </head>

    <body>
        <div>
            <p><a href="/{{fc}}" class='button'>Zurück zum Hauptmenü</a></p>
            <p>{{messages}}</p>
            <h1>{{supplier}} Konfiguration</h1>
            <p><a href="/{{fc}}/{{supplier}}" class='button'>Bearbeiten abbrechen</a></p>
            <form action="/{{fc}}" method="post">
                {{!config_content}}
            </form>
        </div>
    </body>
</html>