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
            <h1>{{configuration}} Konfiguration</h1>
            <form action="/{{fc}}/{{configuration}}" method="post">
                Name: <input name="configuration name" type="text" value="{{configuration}}" required><br/>
                Skript: 
                <select name="Script name" required>
                    {{!script_options}}
                </select><br/>
                Anzahl an Ausführungen, die aufgelistet werden sollen: <input name="number of runs to list" type="number" value="{{number_of_runs_to_list}}" required><br/>
                {{!config_content}}
                <br><br>
                <input type="submit" value="Speichern">
            </form>
            <form action="/{{fc}}/{{configuration}}"><input type='submit' value='Bearbeiten abbrechen'></form>
        </div>
    </body>
</html>