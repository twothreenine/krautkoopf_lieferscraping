# Partial draft. This script is not ready yet.

import importlib
import tabula
import pandas
import re

import base
import foodsoft_article
import foodsoft_article_import

# Inputs this script's methods take
price_list_input = base.Input(name="price_list_input", required=True, accepted_file_types=[".pdf"], input_format="file")

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
        base.Variable(name="ignore articles by name (containing, case-insensitive)", required=False, example=["nektar"]),
        base.Variable(name="strings to replace in article name", required=False, example={"Zwetschen": "Zwetschken", "250g": "", "*": ""}),
        base.Variable(name="piece articles (exact, case-sensitive)", required=False, example={"Chinakohl": 500, "Brokkoli": 300}),
        base.Variable(name="piece articles (containing, case-insensitive)", required=False, example={"knoblauch": 80}),
        base.Variable(name="discount percentage", required=False, example=10)
        ]

class ScriptRun(base.Run):
    def __init__(self, foodcoop, configuration):
        super().__init__(foodcoop=foodcoop, configuration=configuration)
        self.next_possible_methods = [convert_price_list]

    def convert_price_list(self, session, price_list_input):
        config = base.read_config(self.foodcoop, self.configuration)
        supplier_id = config.get("Foodsoft supplier ID")
        discount_percentage = config.get("discount percentage", 0)
        piece_unit_strings = ["Stk", "Stk."]
        other_unit_strings = ["Pkg", "kg", "Kg", " lt", " bd", "bund"]
        category_strings_to_ignore = ["osre", "M"]
        articles_without_price = ["Asiasalatpflanzen (Schnittsalat)"]
        strings_to_remove_in_names = ["\r", "frische", "frisch", " Frisch", "Frisch-", "Frisch!", "-äpfel", "Neu!", "neu!", "!"]
        strings_to_keep_in_names = ["frische Ernte", "neue Ernte"] # TODO: move in article note?
        mispelled_units = {"0,75m ml": "0,75 lt"}
        unit_regex = r"(?:1⁄2|1⁄4|\d+),?\/?\.?\d*\s?g?\s?(?:ml.?)?(?:lt.?)?(?:kg ?)?(?:Pkg.?)?(?:Stk.?)?"

        dfs = tabula.read_pdf(price_list_input, lattice=True, pages='all', encoding='utf-8', pandas_options={'header': None})
        raw_tables = [df.where(df.notnull(), None).values.tolist() for df in dfs]
        raw_tables.pop(0) # header table with information about the farm
        print(raw_tables)
        split_tables = []
        for raw_table in raw_tables:
            if len(raw_table[0]) == 5:
                split_tables.extend(self.split_table(raw_table))
            else:
                split_tables.append(raw_table)

        # for split_table in split_tables:
        #     print(f"Table {str(split_tables.index(split_table))}")
        #     for row in split_table:
        #         print(f"    {str(row)}")

        tables = []
        left_table = True
        for split_table in split_tables:
            if left_table:
                tables.insert(int(split_tables.index(split_table)/2), split_table)
                left_table = False
            else:
                tables.append(split_table)
                left_table = True

        for table in tables:
            print(f"Table {str(tables.index(table))}")
            for row in table:
                print(f"    {str(row)}")

        self.articles = []
        self.categories = []
        self.ignored_categories = []
        self.ignored_articles = []
        self.notifications = []
        current_category = None

        for table in tables:
            for row in table:
                if row[0]:
                    raw_name = str(row[0])
                    names = []
                    price_contents = []
                    if row[1]:
                        price_contents = str(row[1]).replace(",", ".").split("\r")
                    if re.search(r"        \d,?\d\d", raw_name):
                        rows = raw_name.split("\r")
                        for row in rows:
                            row_contents = row.split("        ")
                            names.append(row_contents[0])
                            price_contents.append(row_contents[1])
                    elif len(price_contents) > 1:
                        names = raw_name.split("\r")
                    else:
                        names = [raw_name]
                    if not row[1] and not price_contents:
                        category = base.Category(name=str(row[0]))
                        if "GEMÜSE - " in category.name:
                            category.name = "Obst & Gemüse"
                        self.categories.append(category)
                        current_category = category
                    else:
                        prices = []
                        for price_content in price_contents:
                            try:
                                prices.append(float(price_content.strip()))
                            except ValueError:
                                print(f"Price could not be converted to float: {price_content.strip()}")
                                continue
                        if len(prices) > 1 and len(names) == 1:
                            names = raw_name.split("\r")
                        if len(prices) != len(names):
                            print("Prices and names mismatch:")
                            print(str(names))
                            print(str(prices))
                        else:
                            for name in names:
                                index = names.index(name)
                                name = name.strip()
                                unit = ""
                                price = prices[index]
                                if re.match(r"^\d kg .*", name) or re.search(r"(?:Ab|ab) \d+ (?:kg|Stk)", name): # 5 kg Sack, Ab x Stk.
                                    # TODO: option include_bulk_quantities_of_fresh_goods (only useful when Foodsoft supports quantity discount)
                                    # for now we remove these discount articles
                                    continue
                                elif name == f"100 % echt Fl.": # Aroniasaft
                                    if category_unit_regex_match := re.search(unit_regex, current_category.name):
                                        unit = category_unit_regex_match.group(0)
                                        current_category.name = current_category.name.replace(category_unit_regex_match.group(0), "")
                                    name = f"{current_category.name} 100 %"
                                for string in strings_to_remove_in_names:
                                    remove_string = True
                                    for string_to_keep in strings_to_keep_in_names:
                                        if string in string_to_keep:
                                            remove_string = False
                                            break
                                    if remove_string:
                                        name = name.replace(string, "")
                                # name = name.replace('½', '1/2').replace('¼', '1/4') # did not work
                                for piece_unit_string in piece_unit_strings:
                                    if name.endswith(piece_unit_string):
                                        unit = piece_unit_string
                                        break
                                if not unit:
                                    for mispelled_unit in mispelled_units.keys():
                                        if mispelled_unit in name:
                                            unit = mispelled_units[mispelled_unit] # correct one
                                            name = name.replace(mispelled_unit, "")
                                            break
                                    if not unit:
                                        if unit_regex_match := re.search(unit_regex, name):
                                            unit = unit_regex_match.group(0)
                                        else:
                                            for unit_string in other_unit_strings:
                                                if unit_string in name:
                                                    unit = unit_string
                                                    break
                                name = name.replace(unit, "").strip()
                                unit = unit.replace("bd", "Bund").replace("bund", "Bund").strip()
                                if not unit:
                                    if "topf" in name or "Topf" in name:
                                        unit = "Stk"
                                    elif category_unit_regex_match := re.search(unit_regex, current_category.name):
                                        unit = category_unit_regex_match.group(0)
                                        current_category.name.replace(unit, "").strip()
                                    elif "sirup" in name.casefold():
                                        unit = "0,75 lt" # Hollunderblütensirup not in Sirup category
                                    elif current_category.name == self.articles[-1].category:
                                        unit = self.articles[-1].unit
                                        self.notifications.append(f"Keine Einheit für '{name}' gefunden, verwende Einheit des vorherigen Artikels der gleichen Kategorie ({unit}).")
                                    else:
                                        unit = "Stk"
                                        self.notifications.append(f"Keine Einheit für '{name}' gefunden, verwende Einheit {unit}.")
                                while name.endswith(".") or name.endswith(","):
                                    name = name[:-1].strip()
                                while unit.endswith(".") or unit.endswith(","):
                                    unit = unit[:-1].strip()
                                if re.search(r"\d,\d+\s*ml", unit):
                                    unrealistic_unit = unit
                                    unit = unit.replace("ml", "lt")
                                    self.notifications.append(f"Artikel '{name}' hat unrealistische Einheit {unrealistic_unit}, ersetze durch {unit}.")
                                if price >= 100 and current_category.name == self.articles[-1].category:
                                    unrealistic_price = price
                                    price = self.articles[-1].price_net
                                    self.notifications.append(f"Artikel '{name}' hat unrealistischen Preis {str(unrealistic_price)} €, verwende Preis des vorherigen Artikels der gleichen Kategorie ({str(price)} €).")
                                name = name[0].upper() + name[1:] # always capitalize first letter
                                category_name = current_category.name
                                if len(self.categories) == 1:
                                    if "Eier" in name:
                                        category_name = "Eier"
                                    elif "wurst" in name:
                                        category_name = "Wurst"
                                article = foodsoft_article.Article(order_number="", name=name, unit=unit, price_net=price, vat=discount_percentage*-1, category=category_name, orig_unit=unit)
                                self.articles.append(article)

        #             articles.append([str(row[0]).replace('\r', ' ').replace('frisch', '').replace('!', ''), price])
        # for article in articles:
        #     print(article)
        


        # articles_to_ignore_exact = config.get("ignore articles by name (exact, case-sensitive)", [])
        # articles_to_ignore_containing = config.get("ignore articles by name (containing, case-insensitive)", [])
        # strings_to_replace_in_article_name = config.get("strings to replace in article name", {})
        # piece_articles_exact = config.get("piece articles (exact, case-sensitive)", {})
        # piece_articles_containing = config.get("piece articles (containing, case-insensitive)", {})
        # parcels_in_names = config.get("parcels in names", [])
        # self.categories = []
        # self.articles = []
        # self.ignored_categories = []
        # self.ignored_articles = []
        # self.notifications = []

        # generator = price_list.iter_rows(min_row=3)
        # rows = []
        # for row in generator:
        #     new_row = []
        #     for column in row:
        #         new_row.append(column.value)
        #     rows += [new_row]

        # recalculate_unit = True # 500g or Stk. instead of kg, but only for vegetables, not for dry goods

        # category = base.Category(name="Gemüse")
        # self.categories.append(category)
        # for article_row in rows:
        #     if self.articles and not article_row[0]:
        #         recalculate_unit = False
        #         category = base.Category(name="weitere Artikel")
        #         self.categories.append(category)
        #     elif not article_row[0]:
        #         pass
        #     elif "In allen Preisen" in article_row[0]:
        #         break
        #     else:
        #         original_name = article_row[0]
        #         name = base.replace_in_string(original_name, strings_to_replace_in_article_name).strip()
        #         unit = article_row[3].replace("/", "").strip()
        #         for string in parcels_in_names:
        #             if string in name:
        #                 unit = string
        #                 name = name.replace(string, "").strip()
        #         price = float(article_row[2])

        #         article = foodsoft_article.Article(order_number="", name=name, unit=unit, price_net=price, category=name, orig_unit=unit)

        #         if base.equal_strings_check(list1=[name, original_name], list2=articles_to_ignore_exact, case_sensitive=True, strip=False) or base.containing_strings_check(list1=[name, original_name], list2=articles_to_ignore_containing, case_sensitive=False, strip=False):
        #             self.ignored_articles.append(article)
        #         else:
        #             if recalculate_unit and unit in ["1kg", "1 kg", "kg"]:
        #                 matching_piece_articles_exact = base.equal_strings_check(list1=[name, original_name], list2=[str(entry) for entry in piece_articles_exact.keys()], case_sensitive=True, strip=False)
        #                 matching_piece_articles_containing = base.containing_strings_check(list1=[name, original_name], list2=[str(entry) for entry in piece_articles_containing.keys()], case_sensitive=False, strip=False)
        #                 if matching_piece_articles_exact:
        #                     article = self.convert_to_piece_article(article=article, conversion=piece_articles_exact[matching_piece_articles_exact[0]])
        #                 elif matching_piece_articles_containing:
        #                     article = self.convert_to_piece_article(article=article, conversion=piece_articles_containing[matching_piece_articles_containing[0]])
        #                 else:
        #                     article = self.convert_to_500g_article(article=article)

        #             article_hash = hash(f"{original_name}{unit}")
        #             article.order_number = f"{str(self.categories.index(category)).zfill(2)}{str(article_hash)}"

        #             self.articles.append(article)

        # self.articles = foodsoft_article_import.rename_duplicates(self.articles)
        # articles_from_foodsoft = foodsoft_article_import.get_articles_from_foodsoft(supplier_id=supplier_id, foodsoft_connector=session.foodsoft_connector)
        # self.articles, self.notifications = foodsoft_article_import.compare_manual_changes(foodcoop=self.foodcoop, supplier=self.configuration, articles=self.articles, articles_from_foodsoft=articles_from_foodsoft, notifications=self.notifications)
        self.notifications = foodsoft_article_import.write_articles_csv(file_path=base.file_path(path=self.path, folder="download", file_name=self.configuration + "_Artikel_" + self.name), articles=self.articles, notifications=self.notifications)
        message_prefix = config.get("message prefix", "")
        message = foodsoft_article_import.compose_articles_csv_message(supplier=self.configuration, foodsoft_url=session.settings.get('foodsoft_url'), supplier_id=supplier_id, categories=self.categories, ignored_categories=self.ignored_categories, ignored_articles=self.ignored_articles, notifications=self.notifications, prefix=message_prefix)
        base.write_txt(file_path=base.file_path(path=self.path, folder="display", file_name="Zusammenfassung"), content=message)

        # self.next_possible_methods = [mark_as_imported]
        # self.completion_percentage = 80
        # self.log.append(base.LogEntry(action="price list converted", done_by=base.full_user_name(session)))

    def mark_as_imported(self, session):
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

    def split_table(self, raw_table):
        tables = [[], []]
        for row in raw_table:
            tables[0].append([row[0], row[1]])
            right_row = row[2:]
            if right_row[0] == None:
                right_row.pop(0)
            if len(right_row) > 2:
                if right_row[2] == None:
                    right_row.pop(2)
                else:
                    print(f"Right row contains still more than 2 columns: {str(right_row)}")
            tables[1].append(right_row)
            # split_row = False
            # for column in row:
            #     if row.index(column) == 2:
            #         split_row = True
            #     if not split_row:
            #         new_rows[0].append(column)
            #     else:
            #         new_rows[1].append(column)
            # for new_row in new_rows:
            #     if new_row and str(new_row[0]) == "nan":
            #         new_row.pop(0)
            # tables[0].append(new_rows[0])
            # tables[1].append(new_rows[1])
        return tables

if __name__ == "__main__":
    importlib.invalidate_caches()
    script = importlib.import_module("script_krautkoopf_Lebenbauer_import") # I don't know why we have to do this, but if the ScriptRun object is just initialized directly (run = ScriptRun(...)), then it doesn't load when we try to load in web ("AttributeError: Can't get attribute 'ScriptRun' on <module '__main__' from 'web.py'>")
    run = script.ScriptRun(foodcoop="krautkoopf", configuration="Supplier X")
    while run.next_possible_methods:
        func = getattr(run, run.next_possible_methods[0].name)
        func()
    run.save()
