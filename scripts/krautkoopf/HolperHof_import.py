"""
Script for converting a XLSX price list from HolperHof, A-8264 Hainersdorf into a CSV file for upload into Foodsoft.
"""

import openpyxl

import base
import script_libs.generic.foodsoft_article as foodsoft_article
import script_libs.generic.foodsoft_article_import as foodsoft_article_import

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
        base.Variable(name="ignore articles by name (exact, case-sensitive)", required=False, example=["Birnennektar"]),
        base.Variable(name="ignore articles by name (containing, case-insensitive)", required=False, example=["nektar"]),
        base.Variable(name="strings to replace in article name", required=False, example={"Zwetschen": "Zwetschken", "250g": "", "*": ""}),
        base.Variable(name="piece articles (exact, case-sensitive)", required=False, example={"Chinakohl": 500, "Brokkoli": 300}),
        base.Variable(name="piece articles (containing, case-insensitive)", required=False, example={"knoblauch": 80}),
        base.Variable(name="parcels in names", required=False, example=["0,25 l", "0,5 l"]),
        base.Variable(name="recalculate units", required=False, example={"Obst & Gemüse": {"categories": ["Obst & Gemüse"], "original units": ["kg", "1kg", "1 kg"], "replacement units": {"500g": 0.5}}, "Äpfel": {"categories": ["Äpfel"], "original units": ["kg", "1kg", "1 kg"], "replacement units": {"500g": 0.5}}})
        ]

class ScriptRun(base.Run):
    def __init__(self, foodcoop, configuration):
        super().__init__(foodcoop=foodcoop, configuration=configuration)
        self.next_possible_methods = [convert_price_list]

    def convert_price_list(self, session, price_list_input):
        config = base.read_config(self.foodcoop, self.configuration)
        supplier_id = config.get("Foodsoft supplier ID")

        price_list = openpyxl.load_workbook(price_list_input).worksheets[0]
        articles_to_ignore_exact = config.get("ignore articles by name (exact, case-sensitive)", [])
        articles_to_ignore_containing = config.get("ignore articles by name (containing, case-insensitive)", [])
        categories_to_ignore_exact = config.get("ignore categories by name (exact, case-sensitive)", [])
        categories_to_ignore_containing = config.get("ignore categories by name (containing, case-insensitive)", [])
        strings_to_replace_in_article_name = config.get("strings to replace in article name", {})
        piece_articles_exact = config.get("piece articles (exact, case-sensitive)", {})
        piece_articles_containing = config.get("piece articles (containing, case-insensitive)", {})
        parcels_in_names = config.get("parcels in names", [])
        recalculate_units = config.get("recalculate units", {})
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
                new_row.append(column.value)
            rows += [new_row]

        prefix_delimiter = "_"

        category = base.Category(name="Gemüse")
        self.categories.append(category)
        for article_row in rows:
            if self.articles and not article_row[0]:
                category = base.Category(name="weitere Artikel")
                self.categories.append(category)
            elif not article_row[0]:
                pass
            elif "In allen Preisen" in article_row[0] or "Alle Produkte sind" in article_row[0]:
                break
            else:
                original_name = article_row[0]
                name = base.replace_in_string(original_name, strings_to_replace_in_article_name).strip()
                unit = article_row[3].replace("/", "").strip()
                for string in parcels_in_names:
                    if string in name:
                        unit = string
                        name = name.replace(string, "").strip()
                price = float(article_row[2])

                article = foodsoft_article.Article(order_number="", name=name, unit=unit, price_net=price, category=name, orig_unit=unit)

                if base.equal_strings_check(list1=[name, original_name], list2=articles_to_ignore_exact, case_sensitive=True, strip=False) or base.containing_strings_check(list1=[name, original_name], list2=articles_to_ignore_containing, case_sensitive=False, strip=False):
                    self.ignored_articles.append(article)
                else:
                    article_versions = [article]
                    unit_converted = False
                    if category.name == "Gemüse" and unit in ["1kg", "1 kg", "kg"]:
                        matching_piece_articles_exact = base.equal_strings_check(list1=[name, original_name], list2=[str(entry) for entry in piece_articles_exact.keys()], case_sensitive=True, strip=False)
                        matching_piece_articles_containing = base.containing_strings_check(list1=[name, original_name], list2=[str(entry) for entry in piece_articles_containing.keys()], case_sensitive=False, strip=False)
                        if matching_piece_articles_exact:
                            article = self.convert_to_piece_article(article=article, conversion=piece_articles_exact[matching_piece_articles_exact[0]])
                            unit_converted = True
                        elif matching_piece_articles_containing:
                            article = self.convert_to_piece_article(article=article, conversion=piece_articles_containing[matching_piece_articles_containing[0]])
                            unit_converted = True
                    if not unit_converted:
                        article_versions = foodsoft_article_import.recalculate_unit_for_article(article=article, category_names=[category.name], recalculate_units=recalculate_units) # convert to e.g. 500g unit (multiple units possible)

                    for av in article_versions:
                        av.order_number = f"{str(self.categories.index(category)).zfill(2)}{prefix_delimiter}{name}_{av.unit}"
                        self.articles.append(av)

        self.articles, self.notifications = foodsoft_article_import.rename_duplicates(locales=session.locales, articles=self.articles, compare_unit=True, notifications=self.notifications)
        articles_from_foodsoft, self.notifications = foodsoft_article_import.get_articles_from_foodsoft(locales=session.locales, supplier_id=supplier_id, foodsoft_connector=session.foodsoft_connector, prefix_delimiter=prefix_delimiter, notifications=self.notifications)
        self.articles, self.notifications = foodsoft_article_import.compare_manual_changes(locales=session.locales, foodcoop=self.foodcoop, supplier=self.configuration, articles=self.articles, articles_from_foodsoft=articles_from_foodsoft, prefix_delimiter=prefix_delimiter, notifications=self.notifications)
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

    def convert_to_piece_article(self, article, conversion):
        article.name += f" ({self.kg_price_str(article.price_net)})"
        article.unit = "Stk."
        article.price_net *= conversion / 1000
        return article

    def convert_to_500g_article(self, article):
        article.name += f" ({self.kg_price_str(article.price_net)})"
        article.unit = "500g"
        article.price_net /= 2
        return article

    def kg_price_str(self, article_price):
        return "{:.2f} €/kg".format(article_price).replace(".", ",")
