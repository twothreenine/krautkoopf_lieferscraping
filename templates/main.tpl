<!DOCTYPE html>
<html>
    <head>
        <title>{{foodcoop}} Lieferscraping - Hauptmenü</title>
        <link rel="stylesheet" href="/templates/styles.css" type="text/css">
    </head>

    <body>
        <div>
            <p>{{messages}}</p>
            <h1>{{foodcoop}} Lieferscraping</h1>
            <h2>Skript-Konfigurationen</h2>
            <p>{{!suppliers}}</p>
            <form action="/{{fc}}" method="post">
                <input name="new supplier" value="Neue Konfiguration anlegen" type="submit" />
            </form>
            <br/>
            <form action="/{{fc}}" method="post">
                <input name="logout" value="Abmelden" type="submit" />
            </form>
        </div>
    </body>
</html>