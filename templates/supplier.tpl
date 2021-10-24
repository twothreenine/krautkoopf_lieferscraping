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
            <h1>{{supplier}}</h1>
            <p><a href="/{{fc}}/{{supplier}}/run" class='button'>Skript jetzt ausführen</a></p>
            <h2>Zuletzt erstellte CSVs</h2>
            <p>{{!output_content}}</p>
            <h2>Konfiguration</h2>
            <p><a href="/{{fc}}/{{supplier}}/edit" class='button'>Bearbeiten</a></p>
            <p>{{!config_content}}</p>
        </div>
    </body>
</html>