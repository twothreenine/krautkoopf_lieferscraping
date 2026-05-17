"""
Script for converting a PDF price list from Biohof Lebenbauer, A-8230 Hartberg into a CSV file for upload into Foodsoft.
"""

import tabula
import pandas
import re

import base
import script_libs.generic.foodsoft_article as foodsoft_article
import script_libs.generic.foodsoft_article_import as foodsoft_article_import

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
        base.Variable(name="article details", required=False, example={"Kategorie 1": {"exact": False, "case-sensitive": False, "categories": ["Brot"], "origin": "eigen", "manufacturer": "Biohof Lebenbauer"}}),
        base.Variable(name="article details rest", required=False, example={"origin": "unbekannt", "manufacturer": "unbekannt"}),
        base.Variable(name="category numbering", required=False, example={{"Gemüse": "00"}, {"Frisch Gekochtes & Pilze": "01"}})
        ]

class ScriptRun(base.Run):
    def __init__(self, foodcoop, configuration):
        super().__init__(foodcoop=foodcoop, configuration=configuration)
        self.next_possible_methods = [convert_price_list]

    def convert_price_list(self, session, price_list_input):
        config = base.read_config(self.foodcoop, self.configuration)
        supplier_id = config.get("Foodsoft supplier ID")
        conf = Config()
        conf.discount_percentage = config.get("discount percentage", 0)
        conf.piece_unit_strings = config.get("piece unit strings", [])
        conf.other_unit_strings = config.get("other unit strings", [])
        conf.category_strings_to_ignore = config.get("category strings to ignore", [])
        conf.articles_without_price = config.get("articles without price", [])
        conf.strings_to_remove_in_names = config.get("strings to remove in names", [])
        conf.strings_to_keep_in_names = config.get("strings to keep in names", []) # TODO: move in article note?
        conf.mispelled_units = config.get("mispelled units", {})
        conf.articles_to_ignore_exact = config.get("ignore articles by name (exact, case-sensitive)", [])
        conf.articles_to_ignore_containing = config.get("ignore articles by name (containing, case-insensitive)", [])
        conf.categories_to_ignore_exact = config.get("ignore categories by name (exact, case-sensitive)", [])
        conf.categories_to_ignore_containing = config.get("ignore categories by name (containing, case-insensitive)", [])
        conf.piece_articles_exact = config.get("piece articles per category (exact, case-sensitive)", {})
        conf.piece_articles_containing = config.get("piece articles per category (containing, case-insensitive)", {})
        conf.recalculate_units = config.get("recalculate units", {})
        conf.resort_articles_in_categories = config.get("resort articles in categories", {})
        conf.article_details = config.get("article details", {})
        conf.article_details_rest = config.get("article details rest", {})
        self.category_numbering = config.get("category numbering", {})
        conf.unit_regex = r"(?!\d*\s?\%)(?:1⁄2|1⁄4|\d+),?\/?\.?\d*\s?g?\s?(?:ml.?)?(?:lt.?)?(?:d?kg ?)?(?:Kg ?)?(?:Pkg.?)?(?:pkg.?)?(?:Stk.?)?(?:stk.?)?"
        conf.prefix_delimiter = "_"

        dfs = tabula.read_pdf(price_list_input, lattice=True, pages='all', java_options="-Dfile.encoding=ISO-8859-1", encoding='ISO-8859-1', pandas_options={'header': None, "encoding":"ISO-8859-1"})
        raw_tables = [df.where(df.notnull(), None).values.tolist() for df in dfs]
        raw_tables.pop(0) # header table with information about the farm
        table = raw_tables[0]
        for raw_table in raw_tables[1:]:
            table.extend(raw_table)
        self.categories = []
        category = None
        for row in table:
            if not row[0] and not row[2]:
                continue
            if row[0] and pandas.isna(row[1]) and pandas.isna(row[2]) and pandas.isna(row[3]):
                if category:
                    self.find_category_rows_in_table(table=table, category=category, row=row)
                category = base.Category(name=row[0])
                category.row_index = table.index(row)
                category.raw_rows = []
                self.categories.append(category)
        
        if self.category_numbering:
            self.category_numbering = foodsoft_article_import.insert_category_numbers(category_numbering=self.category_numbering, new_categories=self.categories)
        else:
            for c in self.categories:
                self.category_numbering[c.name] = str(index(c)).zfill(2)

        self.find_category_rows_in_table(table=table, category=category)
        
        for category in self.categories:
            subcategory = None
            subcategories_rows = []
            for row in category.raw_rows:
                if subcategory and pandas.isna(row[1]):
                    self.find_subcategory_rows(category_table=category.raw_rows, subcategory=subcategory, row=row)
                    subcategories_rows.extend(subcategory.rows)
                    subcategory = None
                if row[0] and pandas.isna(row[1]) and row[0] not in conf.category_strings_to_ignore:
                    subcategory = base.Category(name=row[0])
                    subcategory.row_index = category.raw_rows.index(row)
                    subcategory.rows = []
                    category.subcategories.append(subcategory)
            if subcategory:
                self.find_subcategory_rows(category_table=category.raw_rows, subcategory=subcategory)
            category.rows = [row for row in category.raw_rows if row not in subcategories_rows and not pandas.isna(row[0]) and not pandas.isna(row[1])]

        self.articles = []
        self.ignored_categories = []
        self.ignored_articles = []
        self.notifications = []
                
        for category in self.categories:
            if base.equal_strings_check(list1=[category.name], list2=conf.categories_to_ignore_exact, case_sensitive=True, strip=False) or base.containing_strings_check(list1=[category.name], list2=conf.categories_to_ignore_containing, case_sensitive=False, strip=False):
                self.ignored_categories.append(category)
                continue
            category_number = self.category_numbering.get(category.name, "u")
            for row in category.rows:
                self.handle_article_row(category=category, category_number=category_number, row=row, config=conf)
            for subcategory in category.subcategories:
                if base.equal_strings_check(list1=[subcategory.name], list2=conf.categories_to_ignore_exact, case_sensitive=True, strip=False) or base.containing_strings_check(list1=[subcategory.name], list2=conf.categories_to_ignore_containing, case_sensitive=False, strip=False):
                    self.ignored_categories.append(subcategory)
                    continue
                for row in subcategory.rows:
                    self.handle_article_row(category=category, category_number=category_number, row=row, subcategory=subcategory, config=conf)

        self.articles, self.notifications = foodsoft_article_import.rename_duplicates(locales=session.locales, articles=self.articles, notifications=self.notifications, compare_unit=True, keep_full_duplicates=False)
        self.articles, self.notifications = foodsoft_article_import.rename_duplicate_order_numbers(locales=session.locales, articles=self.articles, notifications=self.notifications)
        articles_from_foodsoft, self.notifications = foodsoft_article_import.get_articles_from_foodsoft(locales=session.locales, supplier_id=supplier_id, foodsoft_connector=session.foodsoft_connector, prefix_delimiter=conf.prefix_delimiter, notifications=self.notifications)
        self.articles, self.notifications = foodsoft_article_import.compare_manual_changes(locales=session.locales, foodcoop=self.foodcoop, supplier=self.configuration, articles=self.articles, articles_from_foodsoft=articles_from_foodsoft, prefix_delimiter=conf.prefix_delimiter, notifications=self.notifications)
        self.notifications = foodsoft_article_import.write_articles_csv(locales=session.locales, file_path=base.file_path(path=self.path, folder="download", file_name=self.configuration + "_Artikel_" + self.name), articles=self.articles, notifications=self.notifications)
        message_prefix = config.get("message prefix", "")
        message = foodsoft_article_import.compose_articles_csv_message(locales=session.locales, supplier=self.configuration, foodsoft_url=session.settings.get('foodsoft_url'), supplier_id=supplier_id, categories=self.categories, ignored_categories=self.ignored_categories, ignored_articles=self.ignored_articles, notifications=self.notifications, prefix=message_prefix)
        base.write_txt(file_path=base.file_path(path=self.path, folder="display", file_name="Zusammenfassung"), content=message)

        self.next_possible_methods = [mark_as_imported]
        self.completion_percentage = 80
        self.log.append(base.LogEntry(action="price list converted", done_by=base.full_user_name(session)))

    def mark_as_imported(self, session):
        base.set_config_detail(foodcoop=self.foodcoop, configuration=self.configuration, detail="last imported run", value=self.name)
        base.set_config_detail(foodcoop=self.foodcoop, configuration=self.configuration, detail="category numbering", value=self.category_numbering)

        self.next_possible_methods = []
        self.completion_percentage = 100
        self.log.append(base.LogEntry(action="marked as imported", done_by=base.full_user_name(session)))

    def handle_article_row(self, config, category, category_number, row, subcategory=None):
        name = str(row[0]).strip()
        price = None
        if row[1]:
            price_content = str(row[1]).replace(",", ".").strip()
            try:
                price = float(price_content)
            except ValueError:
                print(f"Price could not be converted to float: {price_content.strip()}")
        elif category.name == self.articles[-1].orig_category:
            price = self.articles[-1].price_net
            self.notifications.append(f"Kein Preis für '{name}' gefunden, verwende Preis des vorherigen Artikels der gleichen Kategorie ({self.articles[-1].name}, {'{:.2f}'.format(price)} €).")
        else:
            self.notifications.append(f"Kein Preis für '{name}' gefunden, bitte Preis manuell ergänzen.")
        
        if not re.match(r"^\d kg .*", name) and not re.search(r"(?:Ab|ab) \d+ ?(?:kg|Stk)", name) and not "sack" in name.casefold(): # 5 kg Sack, Ab x Stk.
            # TODO: option include_bulk_quantities_of_fresh_goods (only useful when Foodsoft supports quantity discount)
            # for now we remove these discount articles
            
            for string in config.strings_to_remove_in_names:
                remove_string = True
                for string_to_keep in config.strings_to_keep_in_names:
                    if string in string_to_keep:
                        remove_string = False
                        break
                if remove_string:
                    name = name.replace(string, "")
            unit = ""
            for piece_unit_string in config.piece_unit_strings:
                if name.casefold().endswith(piece_unit_string.casefold()):
                    unit = piece_unit_string
                    break
            if not unit:
                for mispelled_unit in config.mispelled_units.keys():
                    if mispelled_unit in name:
                        unit = config.mispelled_units[mispelled_unit] # correct one
                        name = name.replace(mispelled_unit, "")
                        break
                if not unit:
                    if unit_regex_match := re.search(config.unit_regex, name):
                        unit = unit_regex_match.group(0)
                    else:
                        for unit_string in config.other_unit_strings:
                            if unit_string.casefold() in name.casefold():
                                unit = unit_string
                                break
            name = re.sub(unit, "", name, flags=re.IGNORECASE).strip().replace("\r", " ")
            unit = unit.replace("bd", "Bund").replace("bund", "Bund").strip()
            if not unit:
                if "topf" in name or "Topf" in name:
                    unit = "Stk"
                elif category_unit_regex_match := re.search(config.unit_regex, category.name):
                    unit = category_unit_regex_match.group(0)
                    category.name.replace(unit, "").strip()
                elif category.name == self.articles[-1].orig_category:
                    unit = self.articles[-1].orig_unit
                    self.notifications.append(f"Keine Einheit für '{name}' gefunden, verwende Originaleinheit des vorherigen Artikels der gleichen Kategorie ({unit}).")
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

            if price:
                if price >= 100 and category.name == self.articles[-1].orig_category:
                    unrealistic_price = price
                    price = self.articles[-1].price_net
                    self.notifications.append(f"Artikel '{name}' hat unrealistischen Preis {str(unrealistic_price)} €, verwende Preis des vorherigen Artikels der gleichen Kategorie ({str(price)} €).")
            name = name[0].upper() + name[1:] # always capitalize first letter
            category_name = category.name
            if "Eier" in name:
                category_name = "Eier"
            elif "wurst" in name:
                category_name = "Wurst"
            elif "chips" in name:
                category_name = "Dörr-Obst"
            product_variant_names = [name]
            name.replace("klein, gewaschen", "klein gewaschen")
            # TODO: improve article splitting for cases like "Kohlrabipfl, Zucchinipfl" ... regex draft: (.*?)(?>\W+oder\s|\W+und\s|\W+o\.|\W+od\.|\W+u\.|\,\-|\,)\W*(\S*)
            if product_variants_regex_match := re.search(r"(.*?)(\S*)\W+(?>oder|o\.|od\.|u\.)\W*(\S*)", name):
                if len(product_variants_regex_match.groups()) == 3 and "Frischkäse" not in name:
                    product_variant_names = []
                    name = product_variants_regex_match.group(1).strip()
                    while name.endswith(".") or name.endswith(","):
                        name = name[:-1].strip()
                    for variant in product_variants_regex_match.groups()[1:]:
                        product_variant_names.append(f"{name} {variant}")
            elif "paprika" in name.casefold() and category_name == "Gemüse":
                variants = name.casefold().replace("(hell)grün", "hellgrün, grün").split(",")
                if variants:
                    product_variant_names = []
                    name = " ".join(variants[0].split(" ")[:-1])
                    variants[0] = variants[0].replace(name, "")
                    if len(name) > 1:
                        name = name[0].upper() + name[1:]
                    for variant in variants:
                        variant_name = variant.strip()
                        if variant_name:
                            product_variant_names.append(f"{name} {variant_name}")
            elif "honig" in category.name.casefold():
                name_parts = name.split("onig")
                print("Original: " + name)
                if len(name_parts) > 1:
                    variants_part = name_parts[-1]
                    variants_part = variants_part.replace(")", "").replace("(", "").replace(".", "").replace(",", "").strip()
                    variants_part = base.remove_double_strings_loop(variants_part, " ")
                    variants = variants_part.split(' ')
                    if variants:
                        product_variant_names = []
                    for variant in variants:
                        variant = f"{variant.strip()}honig"
                        if "biohonig" in name.casefold():
                            variant = f"Bio-{variant}"
                        if "oststeir" in name.casefold():
                            variant = f"Oststeirischer {variant}"
                        product_variant_names.append(variant)
                        print("variant: " + variant)

            # match categories
            target_category_name = foodsoft_article_import.resort_articles_in_categories(article_name=name, category_name=category_name, resort_articles_in_categories=config.resort_articles_in_categories)

            # add article origin and manufacturer information via config
            origin = ""
            manufacturer = ""
            article_details_found = False
            for article_detail_category in config.article_details:
                exact = config.article_details[article_detail_category].get("exact")
                case_sensitive = config.article_details[article_detail_category].get("case-sensitive")
                if exact:
                    if base.equal_strings_check(list1=[category.name, category_name, target_category_name], list2=config.article_details[article_detail_category].get("categories", []), case_sensitive=case_sensitive) or base.equal_strings_check(list1=[name], list2=config.article_details[article_detail_category].get("articles", []), case_sensitive=case_sensitive):
                        origin = config.article_details[article_detail_category].get("origin", "")
                        manufacturer = config.article_details[article_detail_category].get("manufacturer", "")
                        article_details_found = True
                        break
                else:
                    if base.containing_strings_check(list1=[category.name, category_name, target_category_name], list2=config.article_details[article_detail_category].get("categories", []), case_sensitive=case_sensitive) or base.containing_strings_check(list1=[name], list2=config.article_details[article_detail_category].get("articles", []), case_sensitive=case_sensitive):
                        origin = config.article_details[article_detail_category].get("origin", "")
                        manufacturer = config.article_details[article_detail_category].get("manufacturer", "")
                        article_details_found = True
                        break
            if not article_details_found and config.article_details_rest:
                origin = config.article_details_rest.get("origin", "")
                manufacturer = config.article_details_rest.get("manufacturer", "")

            for product_variant in product_variant_names:
                product_variant = product_variant.replace("\r", " ")
                article = foodsoft_article.Article(order_number="", name=product_variant, unit=unit, price_net=price, vat=config.discount_percentage*-1, category=target_category_name, origin=origin, manufacturer=manufacturer, orig_unit=unit, orig_category=category_name)
                if base.equal_strings_check(list1=[name], list2=config.articles_to_ignore_exact, case_sensitive=True, strip=False) or base.containing_strings_check(list1=[name], list2=config.articles_to_ignore_containing, case_sensitive=False, strip=False):
                    self.ignored_articles.append(article)
                else:
                    if unit in ["1kg", "1 kg", "kg"]: # convert to piece unit
                        converted_to_piece_article = False
                        for piece_unit_category in config.piece_articles_exact:
                            if base.equal_strings_check(list1=[category.name, category_name, target_category_name], list2=config.piece_articles_exact[piece_unit_category].get("categories")):
                                piece_units = config.piece_articles_exact[piece_unit_category].get("piece units")
                                matching_piece_articles = base.equal_strings_check(list1=[name], list2=[str(entry) for entry in piece_units.keys()], case_sensitive=True, strip=False)
                                if matching_piece_articles:
                                    article = self.convert_to_piece_article(article=article, conversion=piece_units[matching_piece_articles[0]])
                                    converted_to_piece_article = True
                                    break
                        if not converted_to_piece_article:
                            for piece_unit_category in config.piece_articles_containing:
                                if base.equal_strings_check(list1=[category.name, category_name, target_category_name], list2=config.piece_articles_containing[piece_unit_category].get("categories")):
                                    piece_units = config.piece_articles_containing[piece_unit_category].get("piece units")
                                    matching_piece_articles = base.containing_strings_check(list1=[name], list2=[str(entry) for entry in piece_units.keys()], case_sensitive=False, strip=False)
                                    if matching_piece_articles:
                                        article = self.convert_to_piece_article(article=article, conversion=piece_units[matching_piece_articles[0]])
                                        converted_to_piece_article = True
                                        break

                    articles = foodsoft_article_import.recalculate_unit_for_article(article=article, category_names=[category_name, target_category_name], recalculate_units=config.recalculate_units) # convert to e.g. 500g unit (multiple units possible)
                    for a in articles:
                        a.order_number = f"{category_number}{config.prefix_delimiter}{product_variant}_{a.unit}"
                        self.articles.append(a)

    def find_category_rows_in_table(self, table, category, row=None):
        left_rows = []
        right_rows = []
        for raw_row in self.find_raw_category_rows(table, category, row):
            left_rows.append(raw_row[0:2])
            right_rows.append(raw_row[2:])
        category.raw_rows = left_rows + [[None, None]] + right_rows

    def find_raw_category_rows(self, table, category, row=None):
        if row:
            upper_index = table.index(row)
        else:
            upper_index = -1
        return table[category.row_index + 1 : upper_index]
    
    def find_subcategory_rows(self, category_table, subcategory, row=None):
        subcategory.rows = self.find_raw_category_rows(table=category_table, category=subcategory, row=row)

    def convert_to_piece_article(self, article, conversion):
        article.name += f" ({foodsoft_article_import.base_price_str(article_price=article.price_net, base_unit=article.unit, vat=article.vat)})"
        article.unit = "Stk"
        if article.price_net:
            article.price_net = round(article.price_net * conversion / 1000, 2)
        return article

    def split_table(self, raw_table):
        tables = [[], []]
        for row in raw_table:
            tables[0].append([row[0], row[1]])
            right_row = row[2:]
            if right_row[0] == None or pandas.isna(right_row[0]):
                right_row.pop(0)
            if len(right_row) > 2:
                if right_row[2] == None or pandas.isna(right_row[2]):
                    right_row.pop(2)
                else:
                    print(f"Right row contains still more than 2 columns: {str(right_row)}")
            tables[1].append(right_row)
        return tables

class Config():
    pass
