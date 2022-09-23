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
        base.Variable(name="ignore categories by name (exact, case-sensitive)", required=False, example=["Dörr-Obst", "Brot/Gebäck"]),
        base.Variable(name="ignore categories by name (containing, case-insensitive)", required=False, example=["dörr", "bäck"]),
        base.Variable(name="ignore articles by name (exact, case-sensitive)", required=False, example=["Birnennektar"]),
        base.Variable(name="ignore articles by name (containing, case-insensitive)", required=False, example=["Nektar"]),
        base.Variable(name="strings to replace in article name", required=False, example={"Zwetschen": "Zwetschken", "250g": "", "*": ""})
        ]

class ScriptRun(base.Run):
    def __init__(self, foodcoop, configuration):
        super().__init__(foodcoop=foodcoop, configuration=configuration)
        self.next_possible_methods = [convert_price_list]

    def convert_price_list(self, session, price_list_input):
        config = base.read_config(self.foodcoop, self.configuration)
        supplier_id = config.get("Foodsoft supplier ID")

        price_list = openpyxl.load_workbook(price_list_input).worksheets[0]
        categories_to_ignore_exact = config.get("ignore categories by name (exact, case-sensitive)", [])
        categories_to_ignore_containing = config.get("ignore categories by name (containing, case-insensitive)", [])
        articles_to_ignore_exact = config.get("ignore articles by name (exact, case-sensitive)", [])
        articles_to_ignore_containing = config.get("ignore articles by name (containing, case-insensitive)", [])
        strings_to_replace_in_article_name = config.get("strings to replace in article name", {})
        self.categories = []
        self.articles = []
        self.ignored_categories = []
        self.ignored_articles = []
        self.notifications = []

        generator = price_list.iter_rows(min_row=3)
        rows = []
        for row in generator:
            new_row = []
            for column in row:
                new_row.append({"value": column.value, "bgcolor": column.fill.start_color.index})
            rows += [new_row]

        for row in rows:
            category = row[0]["value"]
            if not category:
                continue
            elif "Kat." in category:
                continue
            elif base.equal_strings_check(list1=[category], list2=categories_to_ignore_exact, case_sensitive=True, strip=False) or base.containing_strings_check(list1=[category], list2=categories_to_ignore_containing, case_sensitive=False, strip=False):
                self.ignored_categories.append(base.Category(name=category))
            elif "Alle Preise" in category:
                break
            else:
                category = base.Category(name=category)
                self.categories.append(category)
                for article_row in rows[rows.index(row)+1:]:
                    if article_row[0]["value"]: # new category
                        break
                    elif article_row[0]["bgcolor"] == "00000000": # article not available
                        continue
                    else: # article available
                        original_name = article_row[2]["value"]
                        name = base.replace_in_string(original_name, strings_to_replace_in_article_name).strip()
                        if "Obst/" in category.name:
                            subcategory = category.name.split("/")[1].strip()
                            if subcategory == "Sonstiges":
                                self.notifications.append("Sonstiges Obst verfügbar, wurde nicht ausgelesen!") # TODO bis Herbst 2023
                            else:
                                name = f"{subcategory} {name}"
                        unit = article_row[1]["value"].strip()
                        price = float(article_row[8]["value"].split("/")[0].replace(",", ".").replace("-", "").strip())
                        deposit = 0
                        note = ""
                        if article_row[7]["value"]:
                            deposit = float(article_row[7]["value"].split("/")[0].replace(",", ".").replace("-", "").replace("€", "").strip())
                            deposit_str = "{:.2f}".format(deposit).replace(".", ",")
                            note = f"inkl. {deposit_str} € Pfand"
                        if "Obst/" in category.name or "Getreide" in category.name:
                            if unit in ["1kg", "1 kg", "kg"]:
                                unit = "500g"
                                price /= 2
                        article_hash = hash(f"{original_name}{unit}")
                        order_number = f"{str(self.categories.index(category)).zfill(2)}{str(article_hash)}"

                        article = foodsoft_article.Article(order_number=order_number, name=name, note=note, unit=unit, price_net=price, category=category.name.split("/")[0], deposit=deposit, orig_unit=unit)

                        if base.equal_strings_check(list1=[name, original_name], list2=articles_to_ignore_exact, case_sensitive=True, strip=False) or base.containing_strings_check(list1=[name, original_name], list2=articles_to_ignore_containing, case_sensitive=False, strip=False):
                            self.ignored_articles.append(article)
                        else:
                            self.articles.append(article)

        self.articles = foodsoft_article_import.rename_duplicates(self.articles)
        articles_from_foodsoft = foodsoft_article_import.get_articles_from_foodsoft(supplier_id=supplier_id, foodsoft_connector=session.foodsoft_connector)
        self.articles, self.notifications = foodsoft_article_import.compare_manual_changes(foodcoop=self.foodcoop, supplier=self.configuration, articles=self.articles, articles_from_foodsoft=articles_from_foodsoft, notifications=self.notifications)
        self.notifications = foodsoft_article_import.write_articles_csv(file_path=base.file_path(path=self.path, folder="download", file_name=self.configuration + "_Artikel_" + self.name), articles=self.articles, notifications=self.notifications)
        message_prefix = config.get("message prefix", "")
        message = foodsoft_article_import.compose_articles_csv_message(supplier=self.configuration, foodsoft_url=session.settings.get('foodsoft_url'), supplier_id=supplier_id, categories=self.categories, ignored_categories=self.ignored_categories, ignored_articles=self.ignored_articles, notifications=self.notifications, prefix=message_prefix)
        base.write_txt(file_path=base.file_path(path=self.path, folder="display", file_name="Zusammenfassung"), content=message)

        self.next_possible_methods = [mark_as_imported]
        self.completion_percentage = 80
        self.log.append(base.LogEntry(action="price list converted", done_by=base.full_user_name(session)))

    def mark_as_imported(self, session):
        self.next_possible_methods = []
        self.completion_percentage = 100
        self.log.append(base.LogEntry(action="marked as imported", done_by=base.full_user_name(session)))

if __name__ == "__main__":
    importlib.invalidate_caches()
    script = importlib.import_module("script_krautkoopf_Apfelland_import") # I don't know why we have to do this, but if the ScriptRun object is just initialized directly (run = ScriptRun(...)), then it doesn't load when we try to load in web ("AttributeError: Can't get attribute 'ScriptRun' on <module '__main__' from 'web.py'>")
    run = script.ScriptRun(foodcoop="krautkoopf", configuration="Supplier X")
    while run.next_possible_methods:
        func = getattr(run, run.next_possible_methods[0].name)
        func()
    run.save()
