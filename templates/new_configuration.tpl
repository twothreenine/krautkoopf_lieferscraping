<!DOCTYPE html>
<html>
    <head>
        <title>{{foodcoop}} Lieferscraping - Neue Konfiguration</title>
        <link rel="stylesheet" href="/templates/styles.css" type="text/css">
    </head>

    <body>
        <div>
            <form action="/{{fc}}"><input type='submit' value='Zurück zum Hauptmenü'></form>
            <p>{{messages}}</p>
            <h1>Neue Konfiguration</h1>
            <form action="/{{fc}}" method="post">
                <p><input name="new config name" type="text" placeholder="Name" required></p>
                <p><select name="script name" required>
                    {{!script_options}}
                </select></p>
                <br><br>
                <input type="submit" value="Konfiguration anlegen">
            </form>
        </div>
    </body>
</html>