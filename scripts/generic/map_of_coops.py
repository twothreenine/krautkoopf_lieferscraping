"""
Takes a CSV of food coops with a latitude,longitude column and puts them onto a open street map in an HTML file.
List of supported icons: https://fontawesome.com/v6/icons up to 6.2.0

Requirements:
pip install geopy
pip install folium
"""

import csv
import folium
from folium import plugins

import base
import foodsoft

# Inputs this script's methods take
coops_csv = base.Input(name="coops_csv", required=False, accepted_file_types=[".csv"], input_format="file")

# Executable script methods
run_script = base.ScriptMethod(name="run_script", inputs=[coops_csv])

def config_variables(): # List of the special config variables this script uses, whether they are required and how they could look like
    return [
        base.Variable(name="map center", required=False, example='Foodcoopstadt, 1234 Beispielland'),
        base.Variable(name="default zoom", required=False, example=8),
        base.Variable(name="scroll wheel zoom", required=False, example=False),
        base.Variable(name="tiles", required=False, example="BasemapAT.grau"),
        base.Variable(name="icon prefix", required=False, example="fa"),
        base.Variable(name="icon", required=False, example="people-group"),
        base.Variable(name="icon color", required=False, example="darkred") # use #700534 for IG color
        ]

class ScriptRun(base.Run):
    def __init__(self, foodcoop, configuration):
        super().__init__(foodcoop=foodcoop, configuration=configuration)
        self.next_possible_methods = [run_script]

    def run_script(self, session, coops_csv=None):
        config = base.read_config(self.foodcoop, self.configuration)
        icon_prefix = config.get("icon prefix", "fa")
        icon = config.get("icon", "people-group")
        icon_color = config.get("icon color", "darkred")

        coops_map = folium.Map(location=[47.38149880363235, 13.395774526243233], zoom_start=config.get("default zoom", 10), scrollWheelZoom=config.get("scroll wheel zoom", False), tiles=config.get("tiles", "OpenStreetMap"))
        plugins.Fullscreen().add_to(coops_map)

        # coops_csv_rows = []
        # for line in coops_csv.readlines():
        #     line = line.decode('utf-8').split(";")
        #     coops_csv_rows.append(line)
        #     print(line)
        # coops_csv_rows = [row.decode('utf-8') for row in csv.DictReader(coops_csv.splitlines())]
        with open("ordergroups.csv", newline='', encoding='utf-8') as csvfile:
            coops_csv_rows = list(csv.reader(csvfile, delimiter=';'))
        for row in coops_csv_rows:
            print(row)
        name_column = coops_csv_rows[0].index("Name")
        location_column = coops_csv_rows[0].index("Latitude,Longitude")
        for row in coops_csv_rows[1:]:
            name = row[name_column]
            location = row[location_column]
            if name:
                if location:
                    name = name.replace("`", "'")
                    website_column = coops_csv_rows[0].index("Homepage")
                    email_column = coops_csv_rows[0].index("E-Mail")
                    zipcode_column = coops_csv_rows[0].index("PLZ")
                    town_column = coops_csv_rows[0].index("Ort")
                    coop = FoodCoop(name=name, location_split=location.split(","), website=row[website_column], email=row[email_column], zipcode=row[zipcode_column], town=row[town_column])
                    popup = folium.Popup(folium.Html(coop.popup_html(), script=True, width=200))
                    folium.Marker(location=[coop.location_split[0], coop.location_split[1]], popup=popup, tooltip=name, icon=folium.Icon(icon=icon, prefix=icon_prefix, color=icon_color)).add_to(coops_map)
            else:
                break

        coops_map.save("coops_map.html")
        
        # TODO: save as downloadable file in folder
        # TODO: display for preview (link to downloadable file, or create file twice?)
        # TODO: option to create public link to file (same or new link) -> new web route for public files (for example '/<fc>/public/<file>')

        # base.write_txt(file_path=base.file_path(path=self.path, folder="display", file_name="Summary"), content="")
        # base.write_txt(file_path=base.file_path(path=self.path, folder="details", file_name="Log"), content="")
        self.next_possible_methods = []
        self.completion_percentage = 100
        self.log.append(base.LogEntry(action="executed", done_by=base.full_user_name(session)))

class FoodCoop:
    def __init__(self, name, location_split, website="", email="", zipcode="", town=""):
        self.name = name
        self.location_split = location_split
        self.website = website
        self.email = email
        self.zipcode = zipcode
        self.town = town

    def popup_html(self):
        # TODO: custom CSS (or in map?)
        html = f"<h4>{self.name}</h4><p><label>📍</label> {self.zipcode} {self.town}</p>"
        if self.website:
            html += f"<p><label>🌐</label> <a href='{self.website}' target='_blank'>{self.website}</a></p>"
        if self.email:
            html += f"<p><label>📧</label> <a href='mailto:{self.email}'>{self.email}</a></p>"

        return html
