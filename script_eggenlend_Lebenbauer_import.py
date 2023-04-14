"""
Script for converting a PDF price list from Biohof Lebenbauer, A-8230 Hartberg into a CSV file for upload into Foodsoft.
"""

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
        base.Variable(name="discount percentage", required=False, example=10),
        base.Variable(name="piece unit strings", required=False, example=["Stk", "Stk."]),
        base.Variable(name="other unit strings", required=False, example=["Pkg", "kg", "Kg", "lt", "bd", "Bund"]),
        base.Variable(name="category strings to ignore", required=False, example=["osre", "M"]),
        base.Variable(name="articles without price", required=False, example=["Asiasalatpflanzen (Schnittsalat)"]),
        base.Variable(name="strings to remove in names", required=False, example=["\r", "frische", "frisch", " Frisch", "Frisch-", "Frisch!", "-äpfel", "Neu!", "neu!", "!"]),
        base.Variable(name="strings to keep in names", required=False, example=["frische Ernte", "neue Ernte"]),
        base.Variable(name="mispelled units", required=False, example={"0,75m ml": "0,75 lt"}),
        base.Variable(name="ignore categories by name (exact, case-sensitive)", required=False, example=["Dörr-Obst", "Brot/Gebäck"]),
        base.Variable(name="ignore categories by name (containing, case-insensitive)", required=False, example=["dörr", "bäck"]),
        base.Variable(name="ignore articles by name (exact, case-sensitive)", required=False, example=["Birnennektar"]),
        base.Variable(name="ignore articles by name (containing, case-insensitive)", required=False, example=["nektar"]),
        # base.Variable(name="keep articles by name (exact, case-sensitive)", required=False, example=["Birnennektar xy"]),
        # base.Variable(name="keep articles by name (containing, case-insensitive)", required=False, example=["Pfirsichnektar"]),
        # base.Variable(name="strings to replace in article name", required=False, example={"Zwetschen": "Zwetschken", "250g": "", "*": ""}),
        base.Variable(name="piece articles per category (exact, case-sensitive)", required=False, example={"Obst & Gemüse": {"Chinakohl": 500, "Brokkoli": 300}}),
        base.Variable(name="piece articles per category (containing, case-insensitive)", required=False, example={"Obst & Gemüse": {"knoblauch": 80}}),
        base.Variable(name="recalculate units", required=False, example={"Obst & Gemüse": {"categories": ["Obst & Gemüse"], "original units": ["kg", "1kg", "1 kg"], "replacement units": {"500g": 0.5}}, "Äpfel": {"categories": ["Äpfel"], "original units": ["kg", "1kg", "1 kg"], "replacement units": {"500g": 0.5}}}),
        base.Variable(name="resort articles in categories", required=False, example={"Kategorie 1": {"exact": False, "case-sensitive": False, "original categories": ["Obst & Gemüse", "Äpfel"], "target categories": {"Fruchtgemüse": ["Zucchini", "tomate"]}}}),
        base.Variable(name="article details", required=False, example={"Kategorie 1": {"exact": False, "case-sensitive": False, "categories": ["Brot"], "origin": "eigen", "manufacturer": "Biohof Lebenbauer"}})
        ]

class ScriptRun(base.Run):
    def __init__(self, foodcoop, configuration):
        super().__init__(foodcoop=foodcoop, configuration=configuration)
        self.next_possible_methods = [convert_price_list]

    def convert_price_list(self, session, price_list_input):
        config = base.read_config(self.foodcoop, self.configuration)
        supplier_id = config.get("Foodsoft supplier ID")
        discount_percentage = config.get("discount percentage", 0)
        piece_unit_strings = config.get("piece unit strings", [])
        other_unit_strings = config.get("other unit strings", [])
        category_strings_to_ignore = config.get("category strings to ignore", [])
        articles_without_price = config.get("articles without price", [])
        strings_to_remove_in_names = config.get("strings to remove in names", [])
        strings_to_keep_in_names = config.get("strings to keep in names", []) # TODO: move in article note?
        mispelled_units = config.get("mispelled units", {})
        articles_to_ignore_exact = config.get("ignore articles by name (exact, case-sensitive)", [])
        articles_to_ignore_containing = config.get("ignore articles by name (containing, case-insensitive)", [])
        categories_to_ignore_exact = config.get("ignore categories by name (exact, case-sensitive)", [])
        categories_to_ignore_containing = config.get("ignore categories by name (containing, case-insensitive)", [])
        piece_articles_exact = config.get("piece articles per category (exact, case-sensitive)", {})
        piece_articles_containing = config.get("piece articles per category (containing, case-insensitive)", {})
        recalculate_units = config.get("recalculate units", {})
        resort_articles_in_categories = config.get("resort articles in categories", {})
        article_details = config.get("article details", {})
        unit_regex = r"(?:1⁄2|1⁄4|\d+),?\/?\.?\d*\s?g?\s?(?:ml.?)?(?:lt.?)?(?:d?kg ?)?(?:Kg ?)?(?:Pkg.?)?(?:pkg.?)?(?:Stk.?)?(?:stk.?)?"

        dfs = tabula.read_pdf(price_list_input, lattice=True, pages='all', encoding='utf-8', pandas_options={'header': None})
        raw_tables = [df.where(df.notnull(), None).values.tolist() for df in dfs]
        raw_tables.pop(0) # header table with information about the farm
        split_tables = []
        for raw_table in raw_tables:
            if len(raw_table[0]) == 5:
                split_tables.extend(self.split_table(raw_table))
            else:
                split_tables.append(raw_table)

        tables = []
        left_table = True
        for split_table in split_tables:
            if left_table:
                tables.insert(int(split_tables.index(split_table)/2), split_table)
                left_table = False
            else:
                tables.append(split_table)
                left_table = True

        self.articles = []
        self.categories = []
        self.ignored_categories = []
        self.ignored_articles = []
        self.notifications = []
        current_category = None
        pasta_column1 = "Weizen"
        pasta_column2 = "Dinkel"
        prefix_delimiter = "_"

        for table in tables:
            for row in table:
                if not row[0]:
                    if "vegan" in current_category.name.casefold() and len(self.categories) > 1:
                        old_category_name = current_category.name
                        schokolade_categories = [cat for cat in self.categories if "schokolade" in cat.name.casefold() and not "vegan" in cat.name.casefold()]
                        if schokolade_categories:
                            current_category = schokolade_categories[0]
                            print(f"Springe von {old_category_name} zurück zu {current_category.name}")
                        else:
                            current_category = base.Category(name="Schokolade")
                            self.ignored_categories.append(current_category)
                else:
                    raw_name = str(row[0])
                    names = []
                    price_contents = []
                    if row[1]:
                        price_contents = str(row[1]).replace(",", ".").split("\r")
                    if re.search(r"\s\s\s\s\s\s\s\s\d,?\d\d", raw_name):
                        rows = raw_name.split("\r")
                        for row in rows:
                            row_contents = row.split("        ")
                            names.append(row_contents[0])
                            price_contents.append(str(row_contents[-1]).replace(",", "."))
                    elif len(price_contents) > 1:
                        names = raw_name.split("\r")
                    else:
                        names = [raw_name]
                    if not row[1] and not price_contents and not raw_name in articles_without_price:
                        if str(row[0]) in category_strings_to_ignore or len(str(row[0])) < 3:
                            continue
                        category = base.Category(name=str(row[0]))
                        if base.equal_strings_check(list1=[category.name], list2=categories_to_ignore_exact, case_sensitive=True, strip=False) or base.containing_strings_check(list1=[category.name], list2=categories_to_ignore_containing, case_sensitive=False, strip=False):
                            self.ignored_categories.append(category)
                        else:
                            if "GEMÜSE - " in category.name:
                                category.name = "Obst & Gemüse"
                            self.categories.append(category)
                        current_category = category
                    else:
                        if current_category in self.ignored_categories:
                            continue
                        prices = []
                        for price_content in price_contents:
                            try:
                                prices.append(float(price_content.strip()))
                            except ValueError:
                                if "Dinkel" in price_content and "Nudel" in current_category.name:
                                    pasta_column2 = "Dinkel"
                                    pasta_column1 = raw_name.replace("Neue", "").strip()
                                    names = []
                                else:
                                    print(f"Price could not be converted to float: {price_content.strip()}")
                                continue
                        if len(prices) > 1 and len(names) == 1:
                            if "Nudel" in current_category.name:
                                pasta_variation = names[0]
                                names[0] = f"{pasta_column2} {pasta_variation}"
                                names.append(f"{pasta_column1} {pasta_variation}")
                            else:
                                names = raw_name.split("\r")
                        if len(prices) != len(names) and not raw_name in articles_without_price:
                            print("Prices and names mismatch:")
                            print(str(names))
                            print(str(prices))
                        else:
                            for name in names:
                                index = names.index(name)
                                name = name.strip()
                                unit = ""
                                if prices:
                                    price = prices[index]
                                elif current_category.name == self.articles[-1].orig_category:
                                    price = self.articles[-1].price_net
                                    self.notifications.append(f"Kein Preis für '{name}' gefunden, verwende Preis des vorherigen Artikels der gleichen Kategorie ({self.articles[-1].name}, {'{:.2f}'.format(price)} €).")
                                else:
                                    price = None
                                    self.notifications.append(f"Kein Preis für '{name}' gefunden, bitte Preis manuell ergänzen.")
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
                                for piece_unit_string in piece_unit_strings:
                                    if name.casefold().endswith(piece_unit_string.casefold()):
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
                                                if unit_string.casefold() in name.casefold():
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
                                    elif current_category.name == self.articles[-1].orig_category:
                                        unit = self.articles[-1].orig_unit
                                        self.notifications.append(f"Keine Einheit für '{name}' gefunden, verwende Originaleinheit des vorherigen Artikels der gleichen Kategorie ({unit}).")
                                    else:
                                        unit = "Stk"
                                        self.notifications.append(f"Keine Einheit für '{name}' gefunden, verwende Einheit {unit}.")
                                if current_category.name == "Äpfel":
                                    if apfel_matches := base.containing_strings_check([name], ["birne", "traube", "pfirsich", "nektarine", "quitte", "zwets"]):
                                        current_category = [c for c in self.categories if c.name == "Obst & Gemüse"][0]
                                    else:
                                        name = f"Äpfel {name}"
                                while name.endswith(".") or name.endswith(","):
                                    name = name[:-1].strip()
                                while unit.endswith(".") or unit.endswith(","):
                                    unit = unit[:-1].strip()
                                if re.search(r"\d,\d+\s*ml", unit):
                                    unrealistic_unit = unit
                                    unit = unit.replace("ml", "lt")
                                    self.notifications.append(f"Artikel '{name}' hat unrealistische Einheit {unrealistic_unit}, ersetze durch {unit}.")
                                if price:
                                    if price >= 100 and current_category.name == self.articles[-1].orig_category:
                                        unrealistic_price = price
                                        if "Nudel" in current_category.name:
                                            current_category_articles = [a for a in self.articles if current_category.name == a.orig_category]
                                            article_base_variation = name.split(" ")[0]
                                            current_category_articles_with_same_base_variation = [a for a in current_category_articles if article_base_variation in a.name]
                                            price = current_category_articles_with_same_base_variation[-1].price_net
                                        else:
                                            price = self.articles[-1].price_net
                                        self.notifications.append(f"Artikel '{name}' hat unrealistischen Preis {str(unrealistic_price)} €, verwende Preis des vorherigen Artikels der gleichen Kategorie ({str(price)} €).")
                                name = name[0].upper() + name[1:] # always capitalize first letter
                                category_name = current_category.name
                                if len(self.categories) == 1:
                                    if "Eier" in name:
                                        category_name = "Eier"
                                    elif "wurst" in name:
                                        category_name = "Wurst"
                                    elif "chips" in name:
                                        category_name = "Dörr-Obst"
                                product_variant_names = [name]
                                if product_variants_regex_match := re.search(r"(.*?)(\S*)\W+oder\W+(\S*)", name):
                                    if len(product_variants_regex_match.groups()) == 3:
                                        product_variant_names = []
                                        name = product_variants_regex_match.group(1).strip()
                                        while name.endswith(".") or name.endswith(","):
                                            name = name[:-1].strip()
                                        for variant in product_variants_regex_match.groups()[1:]:
                                            product_variant_names.append(f"{name} {variant}")
                                elif "paprika" in name.casefold() and category_name == "Obst & Gemüse":
                                    variants = name.casefold().replace("hell- u. dunkelgrün", "hellgrün, dunkelgrün").split(",")
                                    if variants:
                                        product_variant_names = []
                                        name = " ".join(variants[0].split(" ")[:-1])
                                        variants[0] = variants[0].replace(name, "")
                                        name = name[0].upper() + name[1:]
                                        for variant in variants:
                                            variant_name = variant.strip()
                                            if variant_name:
                                                product_variant_names.append(f"{name} {variant_name}")
                                elif "schokolade" in current_category.name.casefold():
                                    if base.containing_strings_check(list1=[name], list2=["Kiwi", "Kräuterseitlinge", "Champignons", "Champions", "Apfelessig"]):
                                        current_category = base.Category(name="Diverses")
                                        self.categories.append(current_category)
                                    else:
                                        product_variant_names = []
                                        name = name.replace("Versch.Sorten:", "").replace("usw", "").strip()
                                        chocolate_variants = name.split(",")
                                        if len(chocolate_variants) == 1 and "\r" in chocolate_variants[0]:
                                            chocolate_variants = chocolate_variants[0].split("\r")
                                        for variant in chocolate_variants:
                                            variant = variant.replace("\r", " ").replace("- ", "-").strip()
                                            while variant.startswith(".") and len(variant) > 1:
                                                variant = variant[1:]
                                            variant = variant.strip()
                                            if variant:
                                                if not base.containing_strings_check(list1=[variant], list2=["schoko", "nougat", "trüffel"]):
                                                    variant = f"{variant}-Schokolade"
                                                if "vegan" in current_category.name.casefold() and not "vollmilch" in variant.casefold() and not "joghurt" in variant.casefold():
                                                    variant = f"{variant} vegan"
                                                product_variant_names.append(variant)
                                elif "honig" in current_category.name.casefold():
                                    name_parts = name.split("(")
                                    if len(name_parts) == 2:
                                        variants_part = name_parts[-1]
                                        variants_part = variants_part.replace(")", "")
                                        variants = variants_part.split(",")
                                        if variants:
                                            product_variant_names = []
                                        for variant in variants:
                                            variant = variant.strip()
                                            if "oststeir" in name.casefold() and "honig" in name.casefold():
                                                variant = f"Oststeirischer {variant}honig"
                                            elif "biohonig" in name.casefold():
                                                variant = f"Bio-{variant}honig"
                                            product_variant_names.append(variant)

                                name = name.replace("\r", " ")

                                # match categories
                                target_category_name = foodsoft_article_import.resort_articles_in_categories(article_name=name, category_name=category_name, resort_articles_in_categories=resort_articles_in_categories)

                                # add article origin and manufacturer information via config
                                origin = ""
                                manufacturer = ""
                                for article_detail_category in article_details:
                                    exact = article_details[article_detail_category].get("exact")
                                    case_sensitive = article_details[article_detail_category].get("case-sensitive")
                                    if exact:
                                        if base.equal_strings_check(list1=[current_category.name, category_name, target_category_name], list2=article_details[article_detail_category].get("categories", []), case_sensitive=case_sensitive):
                                            origin = article_details[article_detail_category].get("origin", "")
                                            manufacturer = article_details[article_detail_category].get("manufacturer", "")
                                            break
                                    else:
                                        if base.containing_strings_check(list1=[current_category.name, category_name, target_category_name], list2=article_details[article_detail_category].get("categories", []), case_sensitive=case_sensitive):
                                            origin = article_details[article_detail_category].get("origin", "")
                                            manufacturer = article_details[article_detail_category].get("manufacturer", "")
                                            break

                                for product_variant in product_variant_names:
                                    product_variant = product_variant.replace("\r", " ")
                                    article = foodsoft_article.Article(order_number="", name=product_variant, unit=unit, price_net=price, vat=discount_percentage*-1, category=target_category_name, origin=origin, manufacturer=manufacturer, orig_unit=unit, orig_category=category_name)
                                    if base.equal_strings_check(list1=[name], list2=articles_to_ignore_exact, case_sensitive=True, strip=False) or base.containing_strings_check(list1=[name], list2=articles_to_ignore_containing, case_sensitive=False, strip=False):
                                        self.ignored_articles.append(article)
                                    else:
                                        if unit in ["1kg", "1 kg", "kg"]: # convert to piece unit
                                            converted_to_piece_article = False
                                            for piece_unit_category, piece_units in piece_articles_exact.items():
                                                if base.equal_strings_check(list1=[current_category.name, category_name, target_category_name], list2=[piece_unit_category]):
                                                    matching_piece_articles = base.equal_strings_check(list1=[name], list2=[str(entry) for entry in piece_units.keys()], case_sensitive=True, strip=False)
                                                    if matching_piece_articles:
                                                        article = self.convert_to_piece_article(article=article, conversion=piece_units[matching_piece_articles[0]])
                                                        converted_to_piece_article = True
                                                        break
                                            if not converted_to_piece_article:
                                                for piece_unit_category, piece_units in piece_articles_containing.items():
                                                    if base.equal_strings_check(list1=[current_category.name, category_name, target_category_name], list2=[piece_unit_category]):
                                                        matching_piece_articles = base.containing_strings_check(list1=[name], list2=[str(entry) for entry in piece_units.keys()], case_sensitive=False, strip=False)
                                                        if matching_piece_articles:
                                                            article = self.convert_to_piece_article(article=article, conversion=piece_units[matching_piece_articles[0]])
                                                            converted_to_piece_article = True
                                                            break

                                        articles = foodsoft_article_import.recalculate_unit_for_article(article=article, category_names=[category_name, target_category_name], recalculate_units=recalculate_units) # convert to e.g. 500g unit (multiple units possible)
                                        for a in articles:
                                            a.order_number = f"{str(self.categories.index(current_category)).zfill(2)}{prefix_delimiter}{product_variant}_{a.unit}"
                                            self.articles.append(a)

        self.articles, self.notifications = foodsoft_article_import.rename_duplicates(locales=session.locales, articles=self.articles, notifications=self.notifications, compare_unit=True, keep_full_duplicates=False)
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

    def convert_to_piece_article(self, article, conversion):
        article.name += f" ({foodsoft_article_import.base_price_str(article_price=article.price_net, base_unit=article.unit)})"
        article.unit = "Stk"
        if article.price_net:
            article.price_net = round(article.price_net * conversion / 1000, 2)
        return article

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
        return tables

if __name__ == "__main__":
    importlib.invalidate_caches()
    script = importlib.import_module("script_eggenlend_Lebenbauer_import") # I don't know why we have to do this, but if the ScriptRun object is just initialized directly (run = ScriptRun(...)), then it doesn't load when we try to load in web ("AttributeError: Can't get attribute 'ScriptRun' on <module '__main__' from 'web.py'>")
    run = script.ScriptRun(foodcoop="krautkoopf", configuration="Supplier X")
    while run.next_possible_methods:
        func = getattr(run, run.next_possible_methods[0].name)
        func()
    run.save()
