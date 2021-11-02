<!DOCTYPE html>
<html>
    <head>
        <title>{{foodcoop}} Lieferscraping - {{configuration}}</title>
        <link rel="stylesheet" href="/templates/styles.css" type="text/css">
    </head>

    <body>
        <div>
            <form action="/{{fc}}"><input type='submit' value='Zurück zum Hauptmenü'></form>
            <p>{{messages}}</p>
            <h1>{{configuration}}</h1>
            <form action="/{{fc}}/{{configuration}}/run"><input type='submit' value='Skript ausführen'></form>
            <h2>Letzte Ausführungen</h2>
            <p>{{!output_content}}</p>
            <h2>Konfiguration</h2>
            <p><form action="/{{fc}}/{{configuration}}/edit"><input type='submit' value='Bearbeiten'></form>
            {{!config_content}}</p>
        </div>
    </body>
</html>