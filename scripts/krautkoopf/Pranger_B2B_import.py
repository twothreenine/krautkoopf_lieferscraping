"""
Script for converting a B2B price list (.xlsx) from Biohof Pranger, A-8354 St. Anna am Aigen and creating a CSV file for article upload into Foodsoft.
A separate CSV file for stock article assessment will be created (prices of 0, only long-life "dry" articles).
"""

import openpyxl
import re
import copy
import datetime
import dateutil

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
        base.Variable(name="Foodsoft stock assessment supplier ID", required=False, example=12),
        base.Variable(name="last imported run", required=False),
        base.Variable(name="message prefix", required=False, example="Hallo"),
        base.Variable(name="end heading (containing, case-insensitive)", required=False, example="Wir freuen uns"),
        base.Variable(name="ignore categories by name (exact, case-sensitive)", required=False, example=["Tomaten & Gurken", "Sauerkraut"]),
        base.Variable(name="ignore categories by name (containing, case-insensitive)", required=False, example=["toma", "kraut"]),
        base.Variable(name="ignore articles by name (exact, case-sensitive)", required=False, example=["Karotten"]),
        base.Variable(name="ignore articles by name (containing, case-insensitive)", required=False, example=["karot"]),
        base.Variable(name="strings to replace in article name", required=False, example={"Zwetschen": "Zwetschken", "250g": "", "*": ""}),
        base.Variable(name="strings to replace in article note", required=False, example={"Neu im Sortiment": ""}),
        base.Variable(name="recalculate units", required=False, example={"Obst & Gemüse": {"categories": ["Obst & Gemüse"], "original units": ["kg", "1kg", "1 kg"], "replacement units": {"500g": 0.5}}, "Äpfel": {"categories": ["Äpfel"], "original units": ["kg", "1kg", "1 kg"], "replacement units": {"500g": 0.5}}}),
        base.Variable(name="piece articles (exact, case-sensitive)", required=False, example={"Chinakohl": 500, "Brokkoli": 300}),
        base.Variable(name="piece articles (containing, case-insensitive)", required=False, example={"knoblauch": 80}),
        base.Variable(name="dry goods from category on", required=False, example="Schätze im Glas-Eingemachtes, Brand & Kürbiskernöl"),
        base.Variable(name="resort articles in categories", required=False, example={"Kategorie 1": {"exact": False, "case-sensitive": False, "original categories": ["Obst & Gemüse", "Äpfel"], "target categories": {"Fruchtgemüse": ["Zucchini", "tomate"]}}}),
        base.Variable(name="additional fresh articles", required=False, example={"Article 1 Name": {"unit": "1 kg", "price net": 10.9}, "another article": {"order number": 123, "unit": "1 kg", "unit quantity": 10, "price net": 10.9, "vat": 10, "deposit": 0.5, "category": "Vegetables", "origin": "1234 Place", "manufacturer": "someone", "note": "large pieces", "available": False}}),
        base.Variable(name="additional dry articles", required=False, example={"Article 1 Name": {"unit": "1 kg", "price net": 10.9}, "another article": {"order number": 123, "unit": "1 kg", "unit quantity": 10, "price net": 10.9, "vat": 10, "deposit": 0.5, "category": "Vegetables", "origin": "1234 Place", "manufacturer": "someone", "note": "large pieces", "available": False}})
        ]

class ScriptRun(base.Run):
    def __init__(self, foodcoop, configuration):
        super().__init__(foodcoop=foodcoop, configuration=configuration)
        self.next_possible_methods = [convert_price_list]

    def convert_price_list(self, session, price_list_input):
        config = base.read_config(self.foodcoop, self.configuration)
        supplier_id = config.get("Foodsoft supplier ID")
        stock_assessment_supplier_id = config.get("Foodsoft stock assessment supplier ID")

        price_list = openpyxl.load_workbook(price_list_input).worksheets[0]
        end_heading_containing = config.get("end heading (containing, case-insensitive)", "")
        categories_to_ignore_exact = config.get("ignore categories by name (exact, case-sensitive)", [])
        categories_to_ignore_containing = config.get("ignore categories by name (containing, case-insensitive)", [])
        articles_to_ignore_exact = config.get("ignore articles by name (exact, case-sensitive)", [])
        articles_to_ignore_containing = config.get("ignore articles by name (containing, case-insensitive)", [])
        strings_to_replace_in_article_name = config.get("strings to replace in article name", {})
        strings_to_replace_in_article_note = config.get("strings to replace in article note", {})
        piece_articles_exact = config.get("piece articles (exact, case-sensitive)", {})
        piece_articles_containing = config.get("piece articles (containing, case-insensitive)", {})
        recalculate_units = config.get("recalculate units", {})
        resort_articles_in_categories = config.get("resort articles in categories")
        dry_goods_from_category_on = config.get("dry goods from category on", "")
        additional_fresh_articles = config.get("additional fresh articles", {})
        additional_dry_articles = config.get("additional dry articles", {})
        prefix_delimiter = "_"
        self.categories = []

        self.articles, self.notifications = foodsoft_article_import.create_articles_from_dict(additional_fresh_articles)
        for a in self.articles:
            a.parse_unit(decimal_separator=",")
            if a.parsed_unit and not a.parsed_unit['amount'] == 1:
                a.name += f" ({a.parsed_unit['base_price_with_vat_str']})"

        self.stock_article_candidates = []
        self.ignored_categories = []
        self.ignored_articles = []

        generator = price_list.iter_rows(min_row=21)
        hidden_rows_indeces = [(row - 2 - 23) for row, dimension in price_list.row_dimensions.items() if dimension.hidden] # TODO: update numbers (what do they mean???)
        rows = []
        for row in generator:
            new_row = []
            for column in row:
                if column.border.diagonalUp: # cross-marked cell meaning "not available"
                    new_row.append("X")
                else:
                    new_row.append(column.value)
            rows += [new_row]
        for hri in hidden_rows_indeces:
            rows.pop(hri)

        category = None
        ignore = False
        article = None
        dry_goods = False
        last_article = False
        gift_box_note = ""

        for row in rows:
            column_A = row[0]
            unit_column = row[2]
            column_D = row[3]
            column_E = row[4]
            column_F = row[5]
            
            if not unit_column and base.containing_strings_check(list1=[str(column_A)], list2=[end_heading_containing]):
                last_article = True

            if unit_column or last_article:
                # new article in this row - save article from previous row first
                if article:
                    article.name = base.replace_in_string(article.name, strings_to_replace_in_article_name).strip()

                    if unit_split := re.search(r"(\d+)\s?[x]?(\w*)", article.unit):
                        if len(unit_split.groups()) == 2:
                            article.unit_quantity = int(unit_split.group(1))
                            article.unit = unit_split.group(2)

                    if name_unit_split := re.search(r"([(]?(\d+,?\d*)(\w*[.]?)\S*[)]?\s*)", article.name):
                        if len(name_unit_split.groups()) == 3:
                            whole_unit_string = name_unit_split.group(1)
                            article.name = article.name.replace(whole_unit_string, "").strip()
                            unit_quantifier = name_unit_split.group(2)
                            unit_unit = name_unit_split.group(3)
                            if not dry_goods and unit_unit == "kg" and "," not in unit_quantifier:
                                unit_quantifier_int = int(unit_quantifier)
                                article.unit_quantity *= unit_quantifier_int
                                article.price_net /= unit_quantifier_int
                                article.unit = unit_unit
                            else:
                                article.unit = f"{unit_quantifier} {unit_unit}"
                    
                    if note_unit := re.search(r"(\d+)", article.note):
                        if len(note_unit.groups()) == 1:
                            article.unit_quantity = int(note_unit.group(1))
                    
                    article.orig_name = article.name

                    if article.name in ["Paprika", "Pfefferoni scharf", "Pfefferoni mild", "Zucchini", "Mais", "Rote Rüben"] and dry_goods:
                        article.name += ", eingelegt"

                    converted_to_piece_article = False
                    if not dry_goods:
                        if article.unit in ["kg"]: # convert to piece unit
                            matching_piece_articles = base.equal_strings_check(list1=[article.name], list2=[str(entry) for entry in piece_articles_exact.keys()], case_sensitive=True, strip=False)
                            if matching_piece_articles:
                                article = self.convert_to_piece_article(article=article, conversion=piece_articles_exact[matching_piece_articles[0]])
                                converted_to_piece_article = True
                            if not converted_to_piece_article:
                                matching_piece_articles = base.containing_strings_check(list1=[article.name], list2=[str(entry) for entry in piece_articles_containing.keys()], case_sensitive=False, strip=False)
                                if matching_piece_articles:
                                    article = self.convert_to_piece_article(article=article, conversion=piece_articles_containing[matching_piece_articles[0]])
                                    converted_to_piece_article = True
                    
                    if base.equal_strings_check(list1=[raw_price_unit], list2=["1kg", "1 kg", "kg"]) and base.containing_strings_check(list1=[raw_name, raw_unit], list2=["Pkg"]):
                        article.price_net *= article.unit_quantity

                    if not dry_goods and not converted_to_piece_article:
                        articles = foodsoft_article_import.recalculate_unit_for_article(article=article, category_names=[article.category], recalculate_units=recalculate_units, recalculate_unit_quantity=True) # convert to e.g. 500 g unit (multiple units possible)
                    else:
                        articles = [article]
                                        
                    if len(articles) == 1 and "Geschenkebox" in articles[0].name:
                        base_article = articles[0]
                        today: datetime.date = datetime.date.today()
                        variants: dict = {
                            "Fröhliche Weihnachten": datetime.date(year=today.year, month=12, day=25),
                            "Prosit Neujahr": datetime.date(year=today.year, month=12, day=31),
                            "Alles Liebe zum Valentinstag": datetime.date(year=today.year, month=2, day=14),
                            "Frohe Ostern": dateutil.easter.easter(today.year),
                            "Alles Liebe zum Muttertag": datetime.date(year=today.year, month=5, day=8), # not exact, but sufficient
                            "Alles Liebe zum Vatertag": datetime.date(year=today.year, month=6, day=8) # not exact, but sufficient
                        }
                        max_timespan: datetime.timedelta = datetime.timedelta(days=60)
                        for variant_title, holiday in variants.items():
                            timedelta: datetime.timedelta = holiday - today
                            if timedelta <= max_timespan and timedelta >= datetime.timedelta(days=3):
                                variant_article = copy.deepcopy(article)
                                variant_article.name += f' mit Sticker "{variant_title}"'
                                variant_article.order_number += f'_{variant_title}'
                                articles.append(variant_article)
                        
                        birthday_title = "Alles Liebe zum Geburtstag"
                        base_article.name += f' mit Sticker "{birthday_title}"'
                        base_article.order_number += f'_{birthday_title}'

                    for a in articles:
                        a.category = foodsoft_article_import.resort_articles_in_categories(article_name=a.name, category_name=a.category, resort_articles_in_categories=resort_articles_in_categories)
                        if dry_goods:
                            a.note = ""
                        if "Geschenkebox" in a.name:
                            a.note = gift_box_note
                        if base.equal_strings_check(list1=[a.name, raw_name], list2=articles_to_ignore_exact, case_sensitive=True, strip=False) or base.containing_strings_check(list1=[a.name, raw_name], list2=articles_to_ignore_containing, case_sensitive=False, strip=False):
                            self.ignored_articles.append(a)
                        else:
                            self.articles.append(a)
                            sac = None
                            if dry_goods and a.unit_quantity > 1:
                                sac = self.create_stock_article_candidate(article, supplier_id=supplier_id)
                                self.stock_article_candidates.append(sac)
                            if not re.search(r"[(]\d+,\d+ € \/ \w+[)]", a.name):
                                a.parse_unit(decimal_separator=",")
                                if a.parsed_unit and not a.parsed_unit['amount'] == 1:
                                    appendix = f" ({a.parsed_unit['base_price_with_vat_str']})"
                                    a.name += appendix
                                    if sac:
                                        sac.name += appendix
                    if last_article:
                        break

                if ignore:
                    continue
                raw_unit = unit_column.strip()
                raw_name = column_D.strip()
                if "Geschenkebox" in raw_name:
                    raw_name_split = raw_name.split("\n")
                    gift_box_name_split = raw_name_split[0].split(" *")
                    # gift_box_name = gift_box_name_split[-1]
                    raw_name = gift_box_name_split[0]
                    if len(raw_name_split) > 1:
                        gift_box_note = " ".join(raw_name_split[1:])
                else:
                    raw_name = raw_name.replace("\n", " ")
                raw_note = row[4]
                if raw_note:
                    raw_note = base.replace_in_string(raw_note, strings_to_replace_in_article_note).strip()
                else:
                    raw_note = ""
                if dry_goods:
                    raw_origin = "eigen"
                else:
                    raw_origin = row[5]
                    if raw_origin:
                        raw_origin = raw_origin.strip()
                raw_price_unit = row[7].strip()
                if row[1] == "X":
                    available = False
                else:
                    available = True
                price = row[8]
                if column_A:
                    order_number = str(column_A).strip()
                else:
                    order_number = raw_name
                deposit = 0

                article = foodsoft_article.Article(order_number=order_number, name=raw_name, note=raw_note, unit=raw_unit, price_net=price, vat=10, category=category.name, deposit=deposit, origin=raw_origin, available=available, orig_unit=raw_unit)
            
            elif column_A:
                category_name = column_A.strip()
                if category_name == dry_goods_from_category_on:
                    dry_goods = True
                category = base.Category(name=category_name)
                if base.equal_strings_check(list1=[category.name], list2=categories_to_ignore_exact, case_sensitive=True, strip=False) or base.containing_strings_check(list1=[category.name], list2=categories_to_ignore_containing, case_sensitive=False, strip=False):
                    self.ignored_categories.append(category)
                    ignore = True
                else:
                    self.categories.append(category)
                    ignore = False
            
            else:
                if column_D:
                    column_D = base.replace_in_string(column_D, strings_to_replace_in_article_note).strip()
                    if article.note:
                        article.note = f"{column_D}; {article.note}"
                    else:
                        article.note = column_D
                if column_E and not dry_goods:
                    column_E = base.replace_in_string(column_E, strings_to_replace_in_article_note).strip()
                    if article.note:
                        article.note = f"{column_E}; {article.note}"
                    else:
                        article.note = column_E
                if column_F:
                    article.origin += f" {column_F.strip()}"

        additional_dry_articles, additional_dry_articles_notifications = foodsoft_article_import.create_articles_from_dict(additional_dry_articles)
        self.articles.extend(additional_dry_articles)
        self.notifications.extend(additional_dry_articles_notifications)
        for a in additional_dry_articles:
            sac = self.create_stock_article_candidate(a, supplier_id=supplier_id)
            a.parse_unit(decimal_separator=",")
            if a.parsed_unit and not a.parsed_unit['amount'] == 1:
                appendix = f" ({a.parsed_unit['base_price_with_vat_str']})"
                a.name += appendix
                sac.name += appendix
            self.stock_article_candidates.append(sac)
        
        self.articles, self.notifications = foodsoft_article_import.rename_duplicate_order_numbers(locales=session.locales, articles=self.articles, notifications=self.notifications)
        self.stock_article_candidates, self.notifications = foodsoft_article_import.rename_duplicate_order_numbers(locales=session.locales, articles=self.stock_article_candidates, notifications=self.notifications)
    
        self.articles, self.notifications = foodsoft_article_import.rename_duplicates(locales=session.locales, articles=self.articles, notifications=self.notifications)
        articles_from_foodsoft, self.notifications = foodsoft_article_import.get_articles_from_foodsoft(locales=session.locales, supplier_id=supplier_id, foodsoft_connector=session.foodsoft_connector, prefix_delimiter=prefix_delimiter, notifications=self.notifications)
        self.articles, self.notifications = foodsoft_article_import.compare_manual_changes(locales=session.locales, foodcoop=self.foodcoop, supplier=self.configuration, articles=self.articles, articles_from_foodsoft=articles_from_foodsoft, prefix_delimiter=prefix_delimiter, notifications=self.notifications, last_imported_csv_containing="_artikel")
        self.notifications = foodsoft_article_import.write_articles_csv(locales=session.locales, file_path=base.file_path(path=self.path, folder="download", file_name=self.configuration + "_Artikel_" + self.name), articles=self.articles, notifications=self.notifications)                
        
        self.stock_article_candidates, self.notifications = foodsoft_article_import.rename_duplicates(locales=session.locales, articles=self.stock_article_candidates, notifications=self.notifications)
        stock_article_candidates_from_foodsoft, self.notifications = foodsoft_article_import.get_articles_from_foodsoft(locales=session.locales, supplier_id=stock_assessment_supplier_id, foodsoft_connector=session.foodsoft_connector, prefix_delimiter=prefix_delimiter, notifications=self.notifications)
        self.stock_article_candidates, self.notifications = foodsoft_article_import.compare_manual_changes(locales=session.locales, foodcoop=self.foodcoop, supplier=self.configuration, articles=self.stock_article_candidates, articles_from_foodsoft=stock_article_candidates_from_foodsoft, prefix_delimiter=prefix_delimiter, notifications=self.notifications, last_imported_csv_containing="_lagerartikel")
        self.notifications = foodsoft_article_import.write_articles_csv(locales=session.locales, file_path=base.file_path(path=self.path, folder="download", file_name=self.configuration + "_Lagerartikel_Bedarfserhebung_" + self.name), articles=self.stock_article_candidates, notifications=self.notifications)

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
        pieces_per_package = round(article.unit_quantity * 1000 / conversion)
        piece_conversion = article.unit_quantity * 1000 / pieces_per_package
        article.name += f" ({foodsoft_article_import.base_price_str(article_price=article.price_net, base_unit=article.unit, vat=article.vat)})"
        article.unit = "Stk"
        article.unit_quantity = pieces_per_package
        if article.price_net:
            article.price_net = round(article.price_net * piece_conversion / 1000, 2)
        return article
    
    def create_stock_article_candidate(self, article, supplier_id):
        sac = copy.deepcopy(article)
        sac.unit_quantity = 1
        sac.name += f" - vrsl. {foodsoft_article.value_with_currency_str(sac.price_with_vat, decimal_separator=',')}"
        sac.price_net = 0
        sac.vat = 0
        sac.order_number = f"{str(supplier_id)}_{str(article.order_number)}"
        sac.available = True
        if article.origin == "eigen":
            sac.origin = "Biohof Pranger"
        return sac
