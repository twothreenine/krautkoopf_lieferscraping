<!DOCTYPE html>
<html>
    <head>
        <title>{{foodcoop_name}} Lieferscraping - {{supplier}}</title>
        <link rel="stylesheet" href="/templates/styles.css" type="text/css">
    </head>

    <body>
        <div>
            <h1>{{supplier}}</h1>
            <h2>Zuletzt erstellte CSVs:</h2>
            <p>{{!output_content}}</p>
            <h2>Konfiguration:</h2>
            <p>{{!config_content}}</p>
        </div>
    </body>
</html>