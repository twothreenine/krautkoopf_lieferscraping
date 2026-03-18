"""
Script for reading out the Hofladen PDF price list from Biohof Renner, A-8321 St. Margarethen an der Raab and creating a CSV file for article upload into Foodsoft.
"""

import tabula
import openpyxl

import base
import script_libs.generic.foodsoft_article as foodsoft_article
import script_libs.generic.foodsoft_article_import as foodsoft_article_import

# Inputs this script's methods take
price_list = base.Input(name="price_list", required=True, accepted_file_types=[".xlsx"], input_format="file")

# Executable script methods
convert_price_list = base.ScriptMethod(name="convert_price_list", inputs=[price_list])
mark_as_imported = base.ScriptMethod(name="mark_as_imported")

def config_variables(): # List of the special config variables this script uses, whether they are required and how they could look like
    return [
        base.Variable(name="Foodsoft supplier ID", required=False, example=12),
        base.Variable(name="last imported run", required=False),
        base.Variable(name="ignore categories by name (exact, case-sensitive)", required=False, example=["Dörr-Obst", "Brot/Gebäck"]),
        base.Variable(name="ignore categories by name (containing, case-insensitive)", required=False, example=["dörr", "bäck"]),
        base.Variable(name="ignore articles by name (exact, case-sensitive)", required=False, example=["Birnennektar"]),
        base.Variable(name="ignore articles by name (containing, case-insensitive)", required=False, example=["nektar"]),
        base.Variable(name="ignore articles by origin (exact, case-sensitive)", required=False, example=["Niederösterreich"]),
        base.Variable(name="create loose offers", required=False, example={"all products": {"split amounts from": 5, "split amount into": 0.5}}) # of each product, the offer with the smallest amount >= 5 will be split into units of 0.5 (e.g. kg) and corresponding unit_quantity. Larger offers of the same product will be ignored. TODO: Filter for categories and/or articles
        ]

class ScriptRun(base.Run):
    def __init__(self, foodcoop, configuration):
        super().__init__(foodcoop=foodcoop, configuration=configuration)
        self.next_possible_methods = [convert_price_list]

    def convert_price_list(self, session, price_list):
        config = base.read_config(self.foodcoop, self.configuration)
        supplier_id = config.get("Foodsoft supplier ID")
        categories_to_ignore_exact = config.get("ignore categories by name (exact, case-sensitive)", [])
        categories_to_ignore_containing = config.get("ignore categories by name (containing, case-insensitive)", [])
        articles_to_ignore_exact = config.get("ignore articles by name (exact, case-sensitive)", [])
        articles_to_ignore_containing = config.get("ignore articles by name (containing, case-insensitive)", [])
        sample_amount = config.get("sample amount")
        split_amount_into = config.get("split amount into")
        keep_separate_up_to_largest_amount_of = config.get("keep separate up to largest amount of")

        # had no success with reading out the original PDF (pages 3 and 5 missing), manually copying to XLSX was easier

        # tables = tabula.convert_into(price_list, "renner.csv", output_format="csv", pages="all")
        # dfs = tabula.read_pdf(price_list, lattice=True, pages='all', encoding='ansi', stream=True)
        # print(dfs)
        # raw_tables = [df.where(df.notnull(), None).values.tolist() for df in dfs]
        # # raw_tables.pop(0) # header table with information about the farm
        # for table in raw_tables:
        #     for row in table:
        #         print(row)

        self.articles = []
        self.article_candidates = []
        self.categories = [] # not used
        self.products = []
        self.ignored_articles = []
        self.ignored_categories = [] # not used
        self.notifications = []

        price_list = openpyxl.load_workbook(price_list).worksheets[0]
        generator = price_list.iter_rows()
        for row in generator:
            offer_row = []
            for column in row:
                offer_row.append(column.value)
            if str(offer_row[1]).strip() not in ["", "None", "Einheit in kg"]:
                base_unit = "kg"
                orig_name = str(offer_row[0]).strip()
                name = orig_name
                amount = float(str(offer_row[1]).replace(",", "."))
                unit = f'{str(amount).replace(".", ",").rstrip('0').rstrip(',')} {base_unit}'
                price_net = float(str(offer_row[4]).replace(",", "."))
                vat = 10 #float(str(offer_row[5]).replace(",", "."))
                origin = transform_origin(str(offer_row[6]).strip())
                ean = offer_row[2]
                if ean:
                    order_number =  ean
                else:
                    f"{orig_name}_{str(amount)}"
                if "teigwaren" in name:
                    category = "Teigwaren"
                elif "kerne" in name or "samen" in name:
                    category = "Nüsse und Ölsaaten"
                elif "linsen" in name:
                    category = "Hülsenfrüchte"
                else:
                    category = "Getreide, Mehl, Flocken"
                article = foodsoft_article.Article(order_number=order_number, name=name, unit=unit, price_net=price_net, vat=vat, category=category, origin=origin, amount=amount, base_unit=base_unit, orig_name=orig_name)

                product_found = False
                for p in self.products:
                    if p.name == orig_name:
                        product = p
                        p.articles.append(article)
                        product_found = True
                        break
                if not product_found:
                    product = base.Category(name=orig_name)
                    product.articles = [article]
                    product.open = True
                    self.products.append(product)

        
        for product in self.products:
            product.articles = sorted(product.articles, key=lambda x: x.amount)
            largest = product.articles[-1]
            if largest.amount > keep_separate_up_to_largest_amount_of:
                sample = product.articles[0]
                for article in product.articles:
                    sample = article
                    if article.amount >= sample_amount:
                        break
                base_price = sample.price_net / sample.amount
                sample.name += f" ({foodsoft_article_import.base_price_str(article_price=base_price, base_unit=sample.base_unit, vat=sample.vat, with_decimals=False)})"
                sample.note = ", ".join([f"{a.unit}: {foodsoft_article_import.base_price_str(article_price=a.price_net / a.amount, base_unit=a.base_unit, vat=a.vat)}" for a in product.articles])
                divisor = round(sample.amount / split_amount_into)
                sample.amount /= divisor
                sample.unit = f'{str(sample.amount).replace(".", ",").rstrip('0').rstrip(',')} {base_unit}'
                sample.unit += ' lose'
                sample.price_net = round(sample.price_net / divisor, 2)
                sample.unit_quantity = divisor
                self.article_candidates.append(sample)
            else:
                for article in product.articles:
                    base_price = article.price_net / article.amount
                    article.name += f" ({foodsoft_article_import.base_price_str(article_price=base_price, base_unit=article.base_unit, vat=article.vat, with_decimals=True)})"
                    self.article_candidates.append(article)

        for article in self.article_candidates:
            if base.equal_strings_check(list1=[article.category], list2=categories_to_ignore_exact, case_sensitive=True, strip=False) \
                or base.containing_strings_check(list1=[article.category], list2=categories_to_ignore_containing, case_sensitive=False, strip=False) \
                or base.equal_strings_check(list1=[article.name, article.orig_name, article.order_number], list2=articles_to_ignore_exact, case_sensitive=True, strip=False) \
                or base.containing_strings_check(list1=[article.name, article.orig_name, article.order_number], list2=articles_to_ignore_containing, case_sensitive=False, strip=False):
                
                self.ignored_articles.append(article)
            else:
                self.articles.append(article)

        self.articles, self.notifications = foodsoft_article_import.rename_duplicates(locales=session.locales, articles=self.articles, notifications=self.notifications, compare_unit=True, keep_full_duplicates=True)
        self.articles, self.notifications = foodsoft_article_import.rename_duplicate_order_numbers(locales=session.locales, articles=self.articles, notifications=self.notifications)
        # articles_from_foodsoft, self.notifications = foodsoft_article_import.get_articles_from_foodsoft(locales=session.locales, supplier_id=supplier_id, foodsoft_connector=session.foodsoft_connector, prefix_delimiter=prefix_delimiter, notifications=self.notifications)
        # self.articles, self.notifications = foodsoft_article_import.compare_manual_changes(locales=session.locales, foodcoop=self.foodcoop, supplier=self.configuration, articles=self.articles, articles_from_foodsoft=articles_from_foodsoft, prefix_delimiter=prefix_delimiter, notifications=self.notifications)
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

def transform_origin(origin):
    if origin == "Renner":
        return "eigen"
    elif origin == "NÖ":
        return "Niederösterreich"
    elif origin == "STMK":
        return "Steiermark"
    else:
        return origin
