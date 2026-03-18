"""
Script for converting a price list / availability list from Unser Bauerngarten, A-8047 Graz and creating a CSV file for article upload into Foodsoft.

TODO:
start methods: apply_availability_list (textarea input), convert_price_list (xlsx)

convert_price_list: piece articles etc. anwenden -> foodsoft_articles.Article erstellen, in Config speichern:
    articles:
        <Name>:
            unit: <Einheitstring>
            price_net: <Preis pro Einheit float>
            note: ...
            category: <string>
            ...
            base_price: <string>
Evtl statt piece articles, Kategorien etc in Config festzulegen: CSV erstellen, manuell bearbeiten, dann speichern? oder zusätzlich, um nicht alles bedenken zu müssen

apply_availability_list:
    - Sorten/Artikel trennen nach "," + "und" (doppelt bei Kopfsalat, Ringelblume; Ausnahme Rettich)
    - Ähnlichkeitsprüfung mit Artikeln erst inkl Sorte und dann ohne Sorte
    - wenn kein ähnlicher Artikel gefunden, abfragen -> Auswahlfeld? Option neuen Artikel erstellen
    - Name aus Verfügbarkeitsliste übernehmen, Assoziation speichern?
    - Manual changes speichern (hat Zeit bis nächste Woche)
"""

import openpyxl
import re
import itertools
import difflib
# import datetime
# import dateutil

import base
import script_libs.generic.foodsoft_article as foodsoft_article
import script_libs.generic.foodsoft_article_import as foodsoft_article_import

# Inputs this script's methods take
price_list_input = base.Input(name="price_list_input", required=True, accepted_file_types=[".xlsx"], input_format="file")
availability_list_input = base.Input(name="availability_list_input", required=True, input_format="textarea")
# matching_article_input = base.Input(name="matching_article_input", required=True, input_format="select", options={})

# Executable script methods
convert_price_list = base.ScriptMethod(name="convert_price_list", inputs=[price_list_input])
save_price_list = base.ScriptMethod(name="save_price_list")
apply_availability_list = base.ScriptMethod(name="apply_availability_list", inputs=[availability_list_input])
select_matching_articles = base.ScriptMethod(name="select_matching_articles") # inputs have to be added in method
mark_as_imported = base.ScriptMethod(name="mark_as_imported")

def config_variables(): # List of the special config variables this script uses, whether they are required and how they could look like
    return [
        base.Variable(name="Foodsoft supplier ID", required=False, example=12),
        base.Variable(name="last imported run", required=False),
        base.Variable(name="message prefix", required=False, example="Hallo"),
        base.Variable(name="ignore categories by name (exact, case-sensitive)", required=False, example=["Tomaten & Gurken", "Sauerkraut"]),
        base.Variable(name="ignore categories by name (containing, case-insensitive)", required=False, example=["toma", "kraut"]),
        base.Variable(name="ignore articles by name (exact, case-sensitive)", required=False, example=["Karotten"]),
        base.Variable(name="ignore articles by name (containing, case-insensitive)", required=False, example=["karot"]),
        base.Variable(name="strings to replace in article name", required=False, example={"Zwetschen": "Zwetschken", "250g": "", "*": ""}),
        base.Variable(name="strings to replace in article note", required=False, example={"Neu im Sortiment": ""}),
        base.Variable(name="recalculate units", required=False, example={"Obst & Gemüse": {"categories": ["Obst & Gemüse"], "original units": ["kg", "1kg", "1 kg"], "replacement units": {"500g": 0.5}}, "Äpfel": {"categories": ["Äpfel"], "original units": ["kg", "1kg", "1 kg"], "replacement units": {"500g": 0.5}}}),
        base.Variable(name="piece articles (exact, case-sensitive)", required=False, example={"Chinakohl": 500, "Brokkoli": 300}),
        base.Variable(name="piece articles (containing, case-insensitive)", required=False, example={"knoblauch": 80}),
        base.Variable(name="resort articles in categories", required=False, example={"Kategorie 1": {"exact": False, "case-sensitive": False, "original categories": ["Obst & Gemüse", "Äpfel"], "target categories": {"Fruchtgemüse": ["Zucchini", "tomate"]}}}),
        ]

class OriginalArticle:
    def __init__(self, name, price, unit):
        self.name = name
        self.price = price
        self.unit = unit

class AvailableArticleVariant:
    def __init__(self, name, category, variant=""):
        self.name = name
        self.variant = variant
        self.category = category
        # self.matched_variants = []
        self.matching_price_article = None

    def create_Foodsoft_article(self):
        name = self.name
        if self.variant:
            name += f" {self.variant}"
        order_number = name
        if self.matching_price_article.base_price and self.matching_price_article.base_unit:
            name += f" ({foodsoft_article_import.base_price_str(article_price=self.matching_price_article.base_price, base_unit=self.matching_price_article.base_unit, vat=self.matching_price_article.vat)})"
        return foodsoft_article.Article(order_number = order_number, 
                                        name = name, 
                                        unit = self.matching_price_article.unit, 
                                        price_net = self.matching_price_article.price_net,
                                        note = self.matching_price_article.note, 
                                        manufacturer=self.matching_price_article.manufacturer, 
                                        origin=self.matching_price_article.origin,
                                        vat=self.matching_price_article.vat, 
                                        deposit=self.matching_price_article.deposit, 
                                        unit_quantity=self.matching_price_article.unit_quantity,
                                        category=self.matching_price_article.category)

class UnmatchedAvailableArticleVariant:
    def __init__(self, availableArticle, variant=""):
        self.availableArticle = availableArticle
        self.variant = variant

class ScriptRun(base.Run):
    def __init__(self, foodcoop, configuration):
        super().__init__(foodcoop=foodcoop, configuration=configuration)
        config = base.read_config(self.foodcoop, self.configuration)
        if config.get("last saved price list"):
            self.next_possible_methods = [apply_availability_list, convert_price_list]
        else:
            self.next_possible_methods = [convert_price_list]

    def convert_price_list(self, session, price_list_input):
        config = base.read_config(self.foodcoop, self.configuration)
        price_list = openpyxl.load_workbook(price_list_input).worksheets[0]
        categories_to_ignore_exact = config.get("ignore categories by name (exact, case-sensitive)", [])
        categories_to_ignore_containing = config.get("ignore categories by name (containing, case-insensitive)", [])
        articles_to_ignore_exact = config.get("ignore articles by name (exact, case-sensitive)", [])
        articles_to_ignore_containing = config.get("ignore articles by name (containing, case-insensitive)", [])
        strings_to_replace_in_article_name = config.get("strings to replace in article name", {})
        strings_to_replace_in_article_note = config.get("strings to replace in article note", {})
        piece_articles_exact = config.get("piece articles (exact, case-sensitive)", {})
        piece_articles_containing = config.get("piece articles (containing, case-insensitive)", {})
        recalculate_units = config.get("recalculate units", {})
        resort_articles_in_categories = config.get("resort articles in categories", {})
        prefix_delimiter = "_"
        self.notifications = []
        self.articles = []
        self.original_categories = []
        self.ignored_categories = []
        self.ignored_articles = []

        generator = price_list.iter_rows()
        rows = []
        for row in generator:
            new_row = []
            for column in row:
                new_row.append(column.value)
            rows += [new_row]

        category = None
        ignore = False
        article = None
        last_article = False

        for row in rows:
            if not category and row[0]:
                category = base.Category(name=row[0].replace("Preisliste", "").strip())
                category.original_articles = []
                self.original_categories.append(category)
            elif not row[0]:
                category = None
            elif row[0].strip() == "Kultur":
                continue
            else:
                article = OriginalArticle(name=row[0].strip(), price=row[1], unit=row[2].strip())
                category.original_articles.append(article)

        i = 0
        for row in rows:
            if not row[4]:
                category = None
            elif not row[5]:
                category = base.Category(name=row[4].replace("Preisliste", "").strip())
                category.original_articles = []
                self.original_categories.append(category)
            elif row[4].strip() == "Kultur":
                if not category:
                    category_name = rows[i - 1][0].replace("Preisliste", "").strip()
                    if category_name:
                        category = [c for c in self.original_categories if c.name == category_name][0]
                    else:
                        self.notifications.append(f"No category name found at E{i + 1}")
            else:
                article = OriginalArticle(name=row[4].strip(), price=row[5], unit=row[6].strip())
                category.original_articles.append(article)
            i += 1
        
        # for c in self.original_categories:
        #     print(c.name)
        #     for a in c.original_articles:
        #         print(f"    {a.name} - {a.price} - {a.unit}")

        for original_category in self.original_categories:
            for original_article in original_category.original_articles:
                category = foodsoft_article_import.resort_articles_in_categories(article_name=original_article.name, category_name=original_category.name, resort_articles_in_categories=resort_articles_in_categories)
                article = foodsoft_article.Article(order_number=original_article.name, name=original_article.name, unit=original_article.unit, price_net=original_article.price, category=category, original_article=original_article, original_category=original_category.name)
                article.base_price = None
                article.base_unit = ""
                
                converted_to_piece_article = False
                if article.unit.casefold() in ["kg"]: # convert to piece unit
                    matching_piece_articles = base.equal_strings_check(list1=[article.name], list2=[str(entry) for entry in piece_articles_exact.keys()], case_sensitive=True, strip=False)
                    if matching_piece_articles:
                        article = self.convert_to_piece_article(article=article, conversion=piece_articles_exact[matching_piece_articles[0]])
                        converted_to_piece_article = True
                    if not converted_to_piece_article:
                        matching_piece_articles = base.containing_strings_check(list1=[article.name], list2=[str(entry) for entry in piece_articles_containing.keys()], case_sensitive=False, strip=False)
                        if matching_piece_articles:
                            article = self.convert_to_piece_article(article=article, conversion=piece_articles_containing[matching_piece_articles[0]])
                            converted_to_piece_article = True
                
                if base.equal_strings_check(list1=[article.name], list2=articles_to_ignore_exact, case_sensitive=True, strip=False) or base.containing_strings_check(list1=[article.name], list2=articles_to_ignore_containing, case_sensitive=False, strip=False):
                    self.ignored_articles.append(article)

                if not converted_to_piece_article:
                    articles = foodsoft_article_import.recalculate_unit_for_article(article=article, category_names=[article.category], recalculate_units=recalculate_units, add_base_price_to_name=False) # convert to e.g. 500 g unit (multiple units possible)
                else:
                    articles = [article]
                
                for article in articles:
                    self.articles.append(article)
        
        self.articles, self.notifications = foodsoft_article_import.rename_duplicate_order_numbers(locales=session.locales, articles=self.articles, notifications=self.notifications)

        self.notifications = foodsoft_article_import.write_articles_csv(locales=session.locales, file_path=base.file_path(path=self.path, folder="download", file_name=self.configuration + "_Preisliste_" + self.name), articles=self.articles, notifications=self.notifications)
        message_prefix = config.get("message prefix", "")
        message = foodsoft_article_import.compose_articles_csv_message(locales=session.locales, supplier=self.configuration, foodsoft_url=session.settings.get('foodsoft_url'), categories=self.original_categories, ignored_categories=self.ignored_categories, ignored_articles=self.ignored_articles, notifications=self.notifications, prefix=message_prefix)
        base.write_txt(file_path=base.file_path(path=self.path, folder="display", file_name="Preisliste eingelesen"), content=message)

        self.next_possible_methods = [save_price_list]
        self.completion_percentage = 25
        self.log.append(base.LogEntry(action="marked as imported", done_by=base.full_user_name(session)))

    def save_price_list(self, session):
        base.set_config_detail(foodcoop=self.foodcoop, configuration=self.configuration, detail="last saved price list", value=self.name)

        self.next_possible_methods = [apply_availability_list]
        self.completion_percentage = 50
        self.log.append(base.LogEntry(action="price list saved", done_by=base.full_user_name(session)))

    def apply_availability_list(self, session, availability_list_input):
        availability_list = availability_list_input.split("\n")
        self.available_article_variants = []
        config = base.read_config(self.foodcoop, self.configuration)
        self.notifications = []

        category = None
        for row in availability_list:
            if row.startswith("*") or row.startswith("•⁠⁠⁠⁠"):
                name = row.replace("•⁠⁠", "").replace("*", "").replace("⁠", "").strip()
                variants = []
                if article_variants_regex_match := re.search(r"(.+?) (.+(?= und | oder |\, ).+)", name):
                    name = article_variants_regex_match.group(1)
                    variants_part = article_variants_regex_match.group(2).replace("(", "").replace(")", "")
                    if variants_with_subvariants_regex_match := re.findall(r"(\w+?) (\w+?)(?: und | oder )(\w+)", variants_part):
                        for vws in variants_with_subvariants_regex_match:
                            variant_name = vws[0]
                            for sv in vws[1:]:
                                variants.append(f"{variant_name} {sv}")
                        variants_part = re.sub(r"(\w+?) (\w+?)(?: und | oder )(\w+)\,? ?", "", variants_part)
                    if len(re.findall(" und ", variants_part)) > 1:
                        variant_dimensions = re.findall(r"(\w+\s*\w+)(?: und )(\w+\s*\w+)", variants_part)
                        variants_combinations = list(itertools.product(*variant_dimensions))
                        for vc in variants_combinations:
                            variants.append(" ".join(vc))
                        for vd in variant_dimensions:
                            for vd_variant in vd:
                                variants_part.replace(vd_variant, "")
                    else:
                        more_variants = re.split(" und | oder |, ", variants_part)
                        for mv in more_variants:
                            variants.append(mv)
                            variants_part.replace(mv, "")
                for csa in re.split(r", ", name):
                    for variant in variants:
                        self.available_article_variants.append(AvailableArticleVariant(name=csa, variant=variant, category=category))
                    if not variants:
                        self.available_article_variants.append(AvailableArticleVariant(name=csa, category=category))
            elif row:
                category = row.strip()

        last_run_with_price_list_path, self.notifications = base.get_file_path(foodcoop=self.foodcoop, configuration=self.configuration, run=config.get("last saved price list"), folder="", notifications=self.notifications)
        last_run_with_price_list = self.load(last_run_with_price_list_path)
        self.price_articles = last_run_with_price_list.articles
        self.original_category_names = [oc.name for oc in last_run_with_price_list.original_categories]
        self.price_articles_names = [pa.name for pa in self.price_articles]
        self.unmatched_available_article_variants = []
        
        # match available articles to price articles
        for aav in self.available_article_variants:
            close_matches = []
            if aav.variant:
                a_v = f"{aav.name} {aav.variant}"
                close_matches = difflib.get_close_matches(word=a_v, possibilities=self.price_articles_names, cutoff=0.6)
                if close_matches:
                    self.process_close_matches(available_article_variant=aav, close_matches=close_matches)
            if not aav.variant or not close_matches:
                close_matches = difflib.get_close_matches(word=aav.name, possibilities=self.price_articles_names, cutoff=0.6)
                self.process_close_matches(available_article_variant=aav, close_matches=close_matches)
        
        unmatched_available_article_variants = [aav for aav in self.available_article_variants if not aav.matching_price_article]
        print(unmatched_available_article_variants)
        if unmatched_available_article_variants:
            select_inputs = []
            for uaav in unmatched_available_article_variants:
                select_options = {}
                if uaav.variant:
                    aav_str = f"{uaav.name} {uaav.variant}"
                else:
                    aav_str = uaav.name
                ordered_by_strongest_matches = list(dict.fromkeys(difflib.get_close_matches(word=aav_str, possibilities=self.price_articles_names, cutoff=0.0, n=1000))) # list with unique values
                for price_article_name in ordered_by_strongest_matches:
                    price_articles = [pa for pa in self.price_articles if pa.name == price_article_name]
                    for pa in price_articles:
                        select_options[self.price_articles.index(pa)] = f"{pa.name} - {pa.unit} - {pa.category}"
                select_inputs.append(base.Input(name=f"article{self.available_article_variants.index(uaav)}", required=True, input_format="select", select_options=select_options, description=aav_str))
                global select_matching_articles
                select_matching_articles.inputs = select_inputs

            self.next_possible_methods = [select_matching_articles]
            self.completion_percentage = 62
        else:
            self.create_Foodsoft_articles(session)
    
    def select_matching_articles(self, session, **matching_articles):
        print("select_matching_articles:")
        for ma in matching_articles:
            print(f"  {ma}: {matching_articles[ma]}")
            aav = self.available_article_variants[int(ma.replace("article", ""))]
            pa = self.price_articles[int(matching_articles[ma])]
            print(f"    {aav.name}: {pa.name}")
            aav.matching_price_article = pa
        self.create_Foodsoft_articles(session)

    def create_Foodsoft_articles(self, session):
        config = base.read_config(self.foodcoop, self.configuration)
        prefix_delimiter = "_"
        self.available_foodsoft_articles = []
        for aav in self.available_article_variants:
            self.available_foodsoft_articles.append(aav.create_Foodsoft_article())
        
        self.available_foodsoft_articles, self.notifications = foodsoft_article_import.rename_duplicate_order_numbers(locales=session.locales, articles=self.available_foodsoft_articles, notifications=self.notifications)
        self.available_foodsoft_articles, self.notifications = foodsoft_article_import.rename_duplicates(locales=session.locales, articles=self.available_foodsoft_articles, notifications=self.notifications)
        articles_from_foodsoft, self.notifications = foodsoft_article_import.get_articles_from_foodsoft(locales=session.locales, supplier_id=config.get("Foodsoft supplier ID"), foodsoft_connector=session.foodsoft_connector, prefix_delimiter=prefix_delimiter, notifications=self.notifications)
        self.available_foodsoft_articles, self.notifications = foodsoft_article_import.compare_manual_changes(locales=session.locales, foodcoop=self.foodcoop, supplier=self.configuration, articles=self.available_foodsoft_articles, articles_from_foodsoft=articles_from_foodsoft, prefix_delimiter=prefix_delimiter, notifications=self.notifications)

        self.notifications = foodsoft_article_import.write_articles_csv(locales=session.locales, file_path=base.file_path(path=self.path, folder="download", file_name=self.configuration + "_aktuell_" + self.name), articles=self.available_foodsoft_articles, notifications=self.notifications)
        message_prefix = config.get("message prefix", "")
        message = foodsoft_article_import.compose_articles_csv_message(locales=session.locales, supplier=self.configuration, foodsoft_url=session.settings.get('foodsoft_url'), notifications=self.notifications, prefix=message_prefix)
        base.write_txt(file_path=base.file_path(path=self.path, folder="display", file_name="Verfügbarkeitsliste angewandt"), content=message)

        self.next_possible_methods = [mark_as_imported]
        self.completion_percentage = 75
        self.log.append(base.LogEntry(action="availability list applied", done_by=base.full_user_name(session)))

    def mark_as_imported(self, session):
        base.set_config_detail(foodcoop=self.foodcoop, configuration=self.configuration, detail="last imported run", value=self.name)

        self.next_possible_methods = []
        self.completion_percentage = 100
        self.log.append(base.LogEntry(action="marked as imported", done_by=base.full_user_name(session)))

    def process_close_matches(self, available_article_variant, close_matches):
        closely_matching_price_articles = []
        closest_match = None
        for cm in close_matches:
            closely_matching_price_articles.extend([pa for pa in self.price_articles if pa.name == cm])
        if len(closely_matching_price_articles) > 1:
            close_category_matches = difflib.get_close_matches(word=available_article_variant.category, possibilities=self.original_category_names, cutoff=0.3)
            if close_category_matches:
                closest_match = next((pa for pa in closely_matching_price_articles if pa.original_category in close_category_matches), None)
        if not closest_match and closely_matching_price_articles:
            closest_match = closely_matching_price_articles[0]
        if not closest_match:
            closest_match = next((pa for pa in self.price_articles if pa.name in available_article_variant.name), None)
        if closest_match:
            available_article_variant.matching_price_article = closest_match
            # if available_article_variant.variant:
            #     avstr = f" {available_article_variant.variant}"
            # else:
            #     avstr = ""
            # match_ratio = difflib.SequenceMatcher(a=available_article_variant.name, b=closest_match.name).ratio()
            # if match_ratio < 0.6:
            #     self.notifications.append(f"Achtung: Zuordnung mit geringer Übereinstimmung: {available_article_variant.name}{avstr} ({available_article_variant.category}) -> {closest_match.name} ({closest_match.category}) ({match_ratio})")
            # print(f"{available_article_variant.name}{avstr} ({available_article_variant.category})")
            # print(f"   -> {closest_match.name} ({closest_match.category})")
        # else:
        #     self.unmatched_available_article_variants.append(UnmatchedAvailableArticleVariant(available_article=available_article_variant, variant=available_variant))
        #     print(f"No match found for {available_article_variant.name} {available_variant} ({available_article_variant.category})")

    def convert_to_piece_article(self, article, conversion):
        article.base_price = article.price_net
        article.base_unit = article.unit
        article.unit = "Stk"
        article.price_net *= conversion / 1000
        return article
