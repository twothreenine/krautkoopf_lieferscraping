"""
Script for converting a XLSX price list from Kräuterhof Zach, A-3943 Schrems into a CSV file for upload into Foodsoft.
"""

import openpyxl
import re

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
        articles_to_ignore_exact = config.get("ignore articles by name (exact, case-sensitive)", [])
        articles_to_ignore_containing = config.get("ignore articles by name (containing, case-insensitive)", [])
        strings_to_replace_in_article_name = config.get("strings to replace in article name", {})
        self.categories = []
        self.raw_articles = []
        self.articles = []
        self.ignored_categories = []
        self.ignored_articles = []
        self.notifications = []
        prefix_delimiter = "_"

        generator = price_list.iter_rows()
        rows = []
        for row in generator:
            new_row = []
            for column in row:
                new_row.append({"value": column.value, "tint": column.fill.start_color.tint})
            rows += [new_row]

        jump_over_rows = 0

        for article_row in rows:
            print(article_row[0])
            if jump_over_rows > 0:
                jump_over_rows -= 1
                continue
            if not article_row[0]["value"]:
                pass
            elif base.containing_strings_check(list1=[article_row[0]["value"]], list2=["Vielfalt für Wiederverkäufer", "gültig ab", "Sorte"]):
                pass
            elif article_row[0]["tint"] == -0.249977111117893:
                category_strings = article_row[0]["value"].split("[")
                category = base.Category(name=category_strings[0].strip())
                category.default_unit = None
                if len(category_strings) > 1:
                    unit_matches = re.search(r"\d.*", category_strings[1].replace("]", ""))
                    if unit_matches:
                        category.default_unit = unit_matches[0]
                self.categories.append(category)

                if base.containing_strings_check(list1=[article_row[0]["value"]], list2=["Geschenk", "Box"]):
                    notes = []
                    price = None
                    category_row_index = rows.index(article_row)
                    for row in rows[category_row_index+1:]:
                        if not row[0]["value"]:
                            if notes:
                                break
                            else:
                                pass
                        else:
                            notes.append(row[0]["value"])
                            if row[4]["value"]:
                                price = float(row[4]["value"])
                            last_row_index = rows.index(row)
                    jump_over_rows = last_row_index - category_row_index
                    note = ", ".join(notes)
                    article = foodsoft_article.Article(order_number="", name=category.name, unit=category.default_unit, price_net=price, note=note, category=category.name, orig_unit=category.default_unit)
                    article.category_number = self.categories.index(category)
                    self.raw_articles.append(article)
            else:
                name_string = article_row[0]["value"]
                print(name_string)
                unit_matches = re.search(r"\d.*", name_string)
                if unit_matches:
                    unit = unit_matches[0]
                else:
                    unit = category.default_unit
                original_name = name_string.replace(unit, "").strip()
                name = base.replace_in_string(original_name, strings_to_replace_in_article_name).strip()
                price = float(article_row[4]["value"])

                article = foodsoft_article.Article(order_number="", name=name, unit=unit, price_net=price, category=category.name, orig_unit=unit)
                article.category_number = self.categories.index(category)
                self.raw_articles.append(article)

        for article in self.raw_articles:
            if base.equal_strings_check(list1=[article.name], list2=articles_to_ignore_exact, case_sensitive=True, strip=False) or base.containing_strings_check(list1=[article.name], list2=articles_to_ignore_containing, case_sensitive=False, strip=False):
                self.ignored_articles.append(article)
            else:
                article.order_number = f"{str(article.category_number).zfill(2)}{prefix_delimiter}{article.name}_{article.unit}"
                self.articles.append(article)

        self.articles, self.notifications = foodsoft_article_import.rename_duplicates(locales=session.locales, articles=self.articles, notifications=self.notifications)
        self.articles, self.notifications = foodsoft_article_import.rename_duplicate_order_numbers(locales=session.locales, articles=self.articles, notifications=self.notifications)
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
