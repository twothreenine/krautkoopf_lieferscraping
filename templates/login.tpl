<!DOCTYPE html>
<html>
    <head>
        <title>{{foodcoop}} Lieferscraping - Login</title>
        <link rel="stylesheet" href="/templates/styles.css" type="text/css">
    </head>

    <body>
        <div>
            {{messages}}
            <p>Hallo Mitglied der Foodcoop {{foodcoop}}.
                <br/>Bitte gib das Passwort für folgenden Account ein:
                <br/>{{foodsoft_user}}
                <form action="{{request_path}}" method="post">
                    {{!submitted_form_content}}
                    <input name="password" type="password" />
                    <input value="Anmelden" type="submit" />
                </form>
            </p>
        </div>
    </body>
</html>