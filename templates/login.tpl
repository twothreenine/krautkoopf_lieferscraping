<!DOCTYPE html>
<html>
    <head>
        <title>{{foodcoop_name}} Lieferscraping - Login</title>
        <link rel="stylesheet" href="/templates/styles.css" type="text/css">
    </head>

    <body>
        <div>
            {{messages}}
            <p>Hallo Mitglied der Foodcoop {{foodcoop_name}}.
                <br/>Bitte gib das Passwort für folgenden Account ein:
                <br/>{{foodsoft_user}}
                <form action="/{{foodcoop}}" method="post">
                    <input name="password" type="password" />
                    <input value="Anmelden" type="submit" />
                </form>
            </p>
        </div>
    </body>
</html>