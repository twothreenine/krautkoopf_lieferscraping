"""
Reads the suppliers from your Foodsoft instance, puts them onto a map and saves it as an html file.
In case you want to exclude certain suppliers, you can do that by using supplier categories in Foodsoft.
You can also include the address of your foodcoop base and customly set icons for the markers. List of supported icons: https://fontawesome.com/v4/icons/

Requirements:
pip install geopy
pip install folium
"""

import importlib
from geopy import Nominatim
import folium
from folium import plugins

import base
import foodsoft

# Inputs this script's methods take
# none

# Executable script methods
run_script = base.ScriptMethod(name="run_script")
finish = base.ScriptMethod(name="finish")

def config_variables(): # List of the special config variables this script uses, whether they are required and how they could look like
    return [
        base.Variable(name="map center", required=False, example='Foodcoopstadt, 1234 Beispielland'),
        base.Variable(name="default zoom", required=False, example=11),
        base.Variable(name="scroll wheel zoom", required=False, example=False),
        base.Variable(name="tiles", required=False, example="OpenStreetMap"),
        base.Variable(name="foodcoop addresses", required=False, example={'Foodcoop home': {'description': 'bla blub', 'address': 'Beispielgasse 1, 1234 Beispielland', 'icon': 'home', 'icon-prefix': '', 'icon-color': ''}}, description="One or multiple addresses of the foodcoop itself"),
        base.Variable(name="supplier name prefix delimiters", required=False, example=[') ', '] ']),
        base.Variable(name="supplier name suffix delimiters", required=False, example=[' (', ' [']),
        base.Variable(name="category name prefix delimiters", required=False, example=[') ', '] ']),
        base.Variable(name="category name suffix delimiters", required=False, example=[' (', ' [']),
        base.Variable(name="exclude supplier categories", required=False, example=['inactive', 'dummy']),
        base.Variable(name="style by supplier category", required=False, example={'category 1': {'icon': 'leaf', 'icon-prefix': '', 'icon-color': '', 'show category': True}}),
        base.Variable(name="supplier name field(s)", required=False, example=['custom_fields_public_name', 'name'], description="List of fields which should be checked and used as supplier name if not empty"),
        base.Variable(name="supplier address field(s)", required=False, example=['custom_fields_public_address', 'address'], description="List of fields which should be checked and used as supplier address if not empty"),
        base.Variable(name="supplier website field(s)", required=False, example=['custom_fields_public_homepage', 'url'], description="List of fields which should be checked and used as supplier website link if not empty"),
        base.Variable(name="supplier category field(s)", required=False, example=['supplier_category_id'], description="List of fields (select!) which should be checked and used as supplier category if not empty"),
        base.Variable(name="additional supplier field(s)", required=False, example=[{'foodsoft field(s)': ['custom_fields_public_description'], 'label': ''}, {'foodsoft field(s)': ['custom_fields_ordering_cycle'], 'label': 'Ordering cycle'}], description="Other supplier info which should be added, optionally under the specified label"),
        ]

class ScriptRun(base.Run):
    def __init__(self, foodcoop, configuration):
        super().__init__(foodcoop=foodcoop, configuration=configuration)
        self.next_possible_methods = [run_script]

    def run_script(self, session):
        config = base.read_config(self.foodcoop, self.configuration)
        additional_supplier_fields = base.read_in_config(config, "additional supplier field(s)", [])
        print(additional_supplier_fields)
        suppliers = session.foodsoft_connector.get_supplier_data(name_fields=base.read_in_config(config, "supplier name field(s)", []), \
            address_fields=base.read_in_config(config, "supplier address field(s)", []), \
            website_fields=base.read_in_config(config, "supplier website field(s)", []), \
            category_fields=base.read_in_config(config, "supplier category field(s)", []), \
            additional_fields=additional_supplier_fields, exclude_categories=base.read_in_config(config, "exclude supplier categories", []))
        locator = Nominatim(user_agent="myGeocoder")

        foodcoop_addresses = []
        fc_addresses_dict = base.read_in_config(config, "foodcoop addresses", {})
        for fc_address in fc_addresses_dict.keys():
            address = fc_addresses_dict[fc_address]['address']
            location = locator.geocode(address)
            if location:
                # reusing the Supplier class here, although these are not actually suppliers
                supplier = foodsoft.Supplier(name=fc_address, address=address, additional_fields=[{"value": fc_addresses_dict[fc_address].get("description")}], latitude=location.latitude, longitude=location.longitude, \
                    icon=fc_addresses_dict[fc_address].get("icon"), icon_prefix=fc_addresses_dict[fc_address].get("icon prefix"), icon_color=fc_addresses_dict[fc_address].get("icon color"))
                foodcoop_addresses.append(supplier)

        supplier_name_prefix_delimiters = base.read_in_config(config, "supplier name prefix delimiters", [])
        supplier_name_suffix_delimiters = base.read_in_config(config, "supplier name suffix delimiters", [])
        category_name_prefix_delimiters = base.read_in_config(config, "category name prefix delimiters", [])
        category_name_suffix_delimiters = base.read_in_config(config, "category name suffix delimiters", [])
        style_by_supplier_category = base.read_in_config(config, "style by supplier category", {})

        for supplier in suppliers:
            location = locator.geocode(supplier.address)
            if location:
                supplier.latitude = location.latitude
                supplier.longitude = location.longitude
                for d in supplier_name_prefix_delimiters:
                    supplier.name = supplier.name.split(d)[-1]
                for d in supplier_name_suffix_delimiters:
                    supplier.name = supplier.name.split(d)[0]
                for d in category_name_prefix_delimiters:
                    supplier.category = supplier.category.split(d)[-1]
                for d in category_name_suffix_delimiters:
                    supplier.category = supplier.category.split(d)[0]
                if supplier.category in style_by_supplier_category.keys():
                    supplier.icon = style_by_supplier_category[supplier.category].get('icon')
                    supplier.icon_prefix = style_by_supplier_category[supplier.category].get('icon prefix')
                    supplier.icon_color = style_by_supplier_category[supplier.category].get('icon color')
                    supplier.show_category = style_by_supplier_category[supplier.category].get('show category')
            else:
                suppliers.remove(supplier)
                print(f"Location of supplier {supplier.name} not found ({supplier.address}), supplier removed from map.")

        map_center_address = base.read_in_config(config, "map center", None)
        if map_center_address:
            map_center = locator.geocode(map_center_address)
        elif foodcoop_addresses:
            map_center = foodcoop_addresses[0]
        else:
            pass # TODO: what to do?

        scroll_wheel_zoom = base.read_in_config(config, "scroll wheel zoom", False)
        our_map = folium.Map(location=[map_center.latitude, map_center.longitude], zoom_start=base.read_in_config(config, "default zoom", 11), scrollWheelZoom=scroll_wheel_zoom, tiles=base.read_in_config(config, "tiles", "OpenStreetMap"))
        plugins.Fullscreen().add_to(our_map)

        for fc_address in foodcoop_addresses:
            popup = folium.Popup(folium.Html(popup_html(fc_address), script=True, width=200))
            folium.Marker(location=[fc_address.latitude, fc_address.longitude], popup=popup, tooltip=fc_address.name, icon=folium.Icon(icon=fc_address.icon, prefix=fc_address.icon_prefix, color=fc_address.icon_color)).add_to(our_map)

        for supplier in suppliers:
            popup = folium.Popup(folium.Html(popup_html(supplier), script=True, width=200))
            folium.Marker(location=[supplier.latitude, supplier.longitude], popup=popup, tooltip=supplier.name, icon=folium.Icon(icon=supplier.icon, prefix=supplier.icon_prefix, color=supplier.icon_color)).add_to(our_map)

        our_map.save("map.html")
        # TODO: save as downloadable file in folder
        # TODO: display for preview (link to downloadable file, or create file twice?)
        # TODO: option to create public link to file (same or new link) -> new web route for public files (for example '/<fc>/public/<file>')

        # base.write_txt(file_path=base.file_path(path=self.path, folder="display", file_name="Summary"), content="")
        # base.write_txt(file_path=base.file_path(path=self.path, folder="details", file_name="Log"), content="")
        self.next_possible_methods = []
        self.completion_percentage = 100
        self.log.append(base.LogEntry(action="executed", done_by=base.full_user_name(session)))

def popup_html(supplier, show_category=False):
    # TODO: custom CSS (or in map?)
    html = f"<h4>{supplier.name}</h4><p><label>📍</label> {supplier.address}</p>"
    if supplier.website:
        html += f"<p><label>🌐</label> <a href='{supplier.website}' target='_blank'>{supplier.website}</a></p>"
    if supplier.category and supplier.show_category:
        html += f"<p><label>🗁</label> {supplier.category}</p>"
    for af in supplier.additional_fields:
        value = af.get("value")
        if value:
            html += "<p>"
            label = af.get("label")
            if label:
                html += f"<label>{label}:</label> "
            html += f"{value}</p>"

    return html

if __name__ == "__main__":
    importlib.invalidate_caches()
    script = importlib.import_module("script_generic_test_import") # I don't know why we have to do this, but if the ScriptRun object is just initialized directly (run = ScriptRun(...)), then it doesn't load when we try to load in web ("AttributeError: Can't get attribute 'ScriptRun' on <module '__main__' from 'web.py'>")
    run = script.ScriptRun(foodcoop="krautkoopf", configuration="Supplier X")
    while run.next_possible_methods:
        func = getattr(run, run.next_possible_methods[0].name)
        func()
    run.save()
