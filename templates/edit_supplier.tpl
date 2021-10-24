<!DOCTYPE html>
<html>
    <head>
        <title>{{foodcoop}} Lieferscraping - {{supplier}}</title>
        <link rel="stylesheet" href="/templates/styles.css" type="text/css">
    </head>

    <body>
        <div>
            <form action="/{{fc}}"><input type='submit' value='Zurück zum Hauptmenü'></form>
            <p>{{messages}}</p>
            <h1>{{supplier}} Konfiguration</h1>
            <form action="/{{fc}}/{{supplier}}" method="post">
                Skript: 
                <select name="Script name" required>
                    {{!script_options}}
                </select><br/>
                Foodsoft supplier ID: <input name="Foodsoft supplier ID" type="number" value="{{fs_supplier_id}}"><br/>
                {{!config_content}}
                <br><br>
                <input type="submit" value="Speichern">
            </form>
            <form action="/{{fc}}/{{supplier}}"><input type='submit' value='Bearbeiten abbrechen'></form>
        </div>
    </body>
</html>