"""
Script for converting a XLSX price list from Hiel Feinkost, A-1200 Wien into a CSV file for upload into Foodsoft.
"""

import importlib
import openpyxl

import base
import foodsoft_article
import foodsoft_article_import

# Inputs this script's methods take
price_list_input = base.Input(name="price_list_input", required=True, accepted_file_types=[".xlsx"], input_format="file")

# Executable script methods
convert_price_list = base.ScriptMethod(name="convert_price_list", inputs=[price_list_input])
mark_as_imported = base.ScriptMethod(name="mark_as_imported")

def config_variables(): # List of the special config variables this script uses, whether they are required and how they could look like
    return [
        base.Variable(name="Foodsoft supplier ID", required=False, example=12),
        base.Variable(name="last imported run", required=False),
        base.Variable(name="message prefix", required=False, example="Hallo"),
        base.Variable(name="discount percentage", required=False, example=5),
        base.Variable(name="rename categories", required=False, example={"Weizengluten Spezialitäten": "Seitan", "Snack´s": "Snacks"})
        # base.Variable(name="ignore categories by name (exact, case-sensitive)", required=False, example=["Dörr-Obst", "Brot/Gebäck"]),
        # base.Variable(name="ignore categories by name (containing, case-insensitive)", required=False, example=["dörr", "bäck"]),
        # base.Variable(name="ignore articles by name (exact, case-sensitive)", required=False, example=["Birnennektar"]),
        # base.Variable(name="ignore articles by name (containing, case-insensitive)", required=False, example=["Nektar"]),
        # base.Variable(name="strings to replace in article name", required=False, example={"Zwetschen": "Zwetschken", "250g": "", "*": ""})
        ]

class ScriptRun(base.Run):
    def __init__(self, foodcoop, configuration):
        super().__init__(foodcoop=foodcoop, configuration=configuration)
        self.next_possible_methods = [convert_price_list]

    def convert_price_list(self, session, price_list_input):
        config = base.read_config(self.foodcoop, self.configuration)
        supplier_id = config.get("Foodsoft supplier ID")

        price_list = openpyxl.load_workbook(price_list_input).worksheets[0]
        discount_percentage = config.get("discount percentage", 0)
        # categories_to_ignore_exact = config.get("ignore categories by name (exact, case-sensitive)", [])
        # categories_to_ignore_containing = config.get("ignore categories by name (containing, case-insensitive)", [])
        # articles_to_ignore_exact = config.get("ignore articles by name (exact, case-sensitive)", [])
        # articles_to_ignore_containing = config.get("ignore articles by name (containing, case-insensitive)", [])
        # strings_to_replace_in_article_name = config.get("strings to replace in article name", {})
        # recalculate_units = config.get("recalculate units", {})
        rename_categories = config.get("rename categories", {})
        prefix_delimiter = "_"
        self.categories = []
        self.articles = []
        self.ignored_categories = []
        self.ignored_articles = []
        self.notifications = []
        current_category = None

        generator = price_list.iter_rows(min_row=3)
        rows = []
        for row in generator:
            new_row = []
            for column in row:
                new_row.append(column.value)
            rows += [new_row]

        for row in rows:
            order_number = None
            try:
                order_number = int(row[0])
            except (TypeError, ValueError):
                if row[5]:
                    current_category = base.Category(name=str(row[5]).strip())
                    for key, value in rename_categories.items():
                        if current_category.name == key:
                            current_category.name = value
                            break
                    self.categories.append(current_category)
                else:
                    current_category = None
            if order_number:
                if not current_category:
                    current_category = base.Category()
                    self.categories.append(current_category)
                name = row[1]
                unit = row[4]
                if type(unit) != str:
                    unit = f"{str(unit)}g"
                price = float(row[7]) # use row[15] for 2023 prices
                note = f"{str(row[5])}, mind. {str(row[17])} Wochen haltbar bei {str(row[16])}"
                vat = discount_percentage * -1
                if "Laibchen" in name:
                    current_category.name = "Laibchen"
                elif current_category.name == "Laibchen":
                    name = f"{name} Laibchen"
                elif "röllchen" in name.casefold() or "wurst" in name.casefold():
                    current_category.name = "Veg. Würstchen"
                self.articles.append(foodsoft_article.Article(order_number=order_number, name=name, unit=unit, price_net=price, vat=vat, note=note, category=current_category.name))

        self.articles, self.notifications = foodsoft_article_import.rename_duplicates(locales=session.locales, articles=self.articles, notifications=self.notifications)
        articles_from_foodsoft, self.notifications = foodsoft_article_import.get_articles_from_foodsoft(locales=session.locales, supplier_id=supplier_id, foodsoft_connector=session.foodsoft_connector, notifications=self.notifications)
        self.articles, self.notifications = foodsoft_article_import.compare_manual_changes(locales=session.locales, foodcoop=self.foodcoop, supplier=self.configuration, articles=self.articles, articles_from_foodsoft=articles_from_foodsoft, notifications=self.notifications)
        self.notifications = foodsoft_article_import.write_articles_csv(locales=session.locales, file_path=base.file_path(path=self.path, folder="download", file_name=self.configuration + "_Artikel_" + self.name), articles=self.articles, notifications=self.notifications)
        message_prefix = config.get("message prefix", "")
        message = foodsoft_article_import.compose_articles_csv_message(locales=session.locales, supplier=self.configuration, foodsoft_url=session.settings.get('foodsoft_url'), supplier_id=supplier_id, categories=self.categories, ignored_categories=self.ignored_categories, ignored_articles=self.ignored_articles, notifications=self.notifications, prefix=message_prefix)
        base.write_txt(file_path=base.file_path(path=self.path, folder="display", file_name="Zusammenfassung"), content=message)

        self.next_possible_methods = [mark_as_imported]
        self.completion_percentage = 80
        self.log.append(base.LogEntry(action="price list converted", done_by=base.full_user_name(session)))

    def mark_as_imported(self, session):
        base.set_config_detail(foodcoop=self.foodcoop, configuration=self.configuration, detail="last imported run", value=self.name)

        self.next_possible_methods = []
        self.completion_percentage = 100
        self.log.append(base.LogEntry(action="marked as imported", done_by=base.full_user_name(session)))

if __name__ == "__main__":
    importlib.invalidate_caches()
    script = importlib.import_module("script_krautkoopf_Hiel_import") # I don't know why we have to do this, but if the ScriptRun object is just initialized directly (run = ScriptRun(...)), then it doesn't load when we try to load in web ("AttributeError: Can't get attribute 'ScriptRun' on <module '__main__' from 'web.py'>")
    run = script.ScriptRun(foodcoop="krautkoopf", configuration="Supplier X")
    while run.next_possible_methods:
        func = getattr(run, run.next_possible_methods[0].name)
        func()
    run.save()
