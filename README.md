# krautkoopf_lieferscraping
Automated import of supplier's articles to Foodsoft

Scripts for specific suppliers get data from their webshop (screen-scraping), spreadsheet, etc. and transform it into a CSV which can be imported into Foodsoft. Foodsoft then compares existing articles of this supplier to the new list and shows a summary of changes, deleted articles, and new articles.

## Requirements
python v3.8+

beautifulsoup4

requests v2.24+

bottle v0.12+

dill

pyYAML

## Environment variables
For some optional features, the following enviroment variables need to be set:
- LS_FOODSOFT_URL=
- LS_FOODSOFT_USER=
- LS_FOODSOFT_PASS=

for local use in Windows 10:

- open system settings
- search for "variable"
- select "edit system environment variables" or "edit environment variables for this account" respectively (or similar)
- set variables manually

## Details
Da es in unserer Foodcoop Bedarf gab, den regelmäßigen Aufwand für das Bestellteam zu senken, habe ich ein Python-Skript geschrieben, das sämtliche Artikel einer bestimmten Lieferant_in ausliest (z.B. per Screenscraping aus dem Webshop, aus einer Exceltabelle wäre aber auch denkbar) und daraus eine CSV generiert, die in die Foodsoft importiert werden kann.
Das Screenscraping bzw. Tabelle-auslesen muss natürlich je nach Lieferant/Webshop angepasst bzw. neu geschrieben werden, einige Funktionen (wie das Generieren der CSV) sind jedoch ausgelagert in „base“ und von allen Skripten abrufbar.
Die CSV kann man daraufhin in der Foodsoft über den Button „Artikel hochladen“ (auf der Artikel-Seite des Lieferanten) importieren - dabei sollte man das Häkchen bei „Artikel löschen, die nicht in der hochgeladenen Datei sind“ setzen - woraufhin man eine Zusammenfassung aller Änderungen sieht und diese bestätigen oder korrigieren kann.
Damit dort manuell vorgenommene Korrekturen/Umbenennungen nicht beim nächsten Ausführen des Skriptes wieder rückgängig gemacht werden, hat das Skript auch eine Anbindung an die Foodsoft, über die es sich die bisherige Artikel-CSV herunterlädt und mit der zuletzt erstellten CSV vergleicht. Daten, die seit dem letzten Auslesen gleich geblieben sind, in der Foodsoft aber anders stehen, werden dann aus der Foodsoft übernommen.
Weitere Features:
* Kategorien (z.B. im Webshop) und einzelne Artikel, die nicht importiert werden sollen
* Gleichnamige Artikel umbenennen nach einem Attribut, in dem sie sich unterscheiden (Einheit, Hersteller, Herkunft) - z.B. 2x „Weizenmehl“ → „Weizenmehl (500g)“ und „Weizenmehl (1kg)“, da die Foodsoft gleichnamige Artikel nicht akzeptiert
* Überlange Artikel-Daten (die das jeweilige Zeichenlimit der Foodsoft überschreiten) kürzen

Etwas Ähnliches wurde glaub ich schon mit den Shared Suppliers versucht. Dies ist nun aber dafür gedacht, dass jede Foodcoop individuell Artikel importiert.

## Nächste Schritte
Einfaches Webinterface erstellen, über das die jeweiligen Skripte (inkl. Parametern wie: welche Artikel ignoriert werden sollen) aufgerufen werden können.
