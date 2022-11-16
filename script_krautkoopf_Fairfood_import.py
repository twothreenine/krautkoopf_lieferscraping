"""
Script for reading out the webshop from Fairfood Freiburg (screenscraping) and creating a CSV file for article upload into Foodsoft.
"""

from bs4 import BeautifulSoup
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.firefox import GeckoDriverManager
import xml.etree.ElementTree as ET
import re
import os
import math
from decimal import *

import base
import foodsoft_article
import foodsoft_article_import
import vat

# Inputs this script's methods take
email = base.Input(name="email", required=False, input_format="email", example="example@foo.test")
password = base.Input(name="password", required=False, input_format="password", example="asdf1234")

# Executable script methods
read_webshop = base.ScriptMethod(name="read_webshop", inputs=[email, password])
generate_csv = base.ScriptMethod(name="generate_csv")
mark_as_imported = base.ScriptMethod(name="mark_as_imported")

def config_variables(): # List of the special config variables this script uses, whether they are required and how they could look like
    return [
        base.Variable(name="Foodsoft supplier ID", required=False, example=12),
        base.Variable(name="last imported run", required=False, example="2021-10-27_1"),
        base.Variable(name="country of destination", required=True, example="AT", description="country in which the goods will be delivered (important for VAT calculation)"),
        base.Variable(name="categories to ignore", required=False, example=['Werbematerialien', 'Sparpakete']),
        base.Variable(name="products to ignore", required=False, example=[3, 51]),
        base.Variable(name="articles to ignore", required=False, example=[6700000008, 6700000016]),
        base.Variable(name="message prefix", required=False, example="Hallo"),
        base.Variable(name="discount percentage", required=False, example=5) # TODO: not yet implemented
        ]

class ScriptRun(base.Run):
    def __init__(self, foodcoop, configuration):
        super().__init__(foodcoop=foodcoop, configuration=configuration)
        self.next_possible_methods = [read_webshop]
        self._session = None

    def read_webshop(self, session, email="", password=""):
        config = base.read_config(self.foodcoop, self.configuration)
        self.supplier_id = base.read_in_config(config, "Foodsoft supplier ID", None)
        self.categories_to_ignore = base.read_in_config(config, "categories to ignore", [])
        self.products_to_ignore = base.read_in_config(config, "products to ignore", [])
        self.articles_to_ignore = base.read_in_config(config, "articles to ignore", [])
        exclude_categories_from_loose_orders = base.read_in_config(config, "exclude categories from loose orders", [])

        self.categories = [] # "product types" like "Cashewkerne", which have Products as subcategories (= "item groups" like "Cashewkerne Chili & Paprika")
        self.articles = [] # the selection of offers loaded into foodsoft
        self.ignored_categories = []
        self.ignored_products = []
        self.ignored_articles = []
        self.notifications = [] # notes for the run's info message

        driver = webdriver.Firefox(executable_path=GeckoDriverManager().install()) # Change here if you want use Chromium

        # get B2C prices
        b2c_xml = self.fetch_rss(driver=driver)
        self.parse_articles(driver=driver, config=config, xml=b2c_xml, shop="b2c")

        if email and password:
            self.login(driver=driver, email=email, password=password)
            # after login get B2B prices
            b2b_xml = self.fetch_rss(driver=driver)
            self.parse_articles(driver=driver, config=config, xml=b2b_xml, shop="b2b")


        for category in self.categories:
            for product in category.subcategories:
                offers = sorted(product.offers, key=lambda x: x.content_grm)
                loose_offers_count = 0
                for offer in offers:
                    content_grm = offer.content_grm
                    offers_of_same_amount = sorted([o for o in offers if o.content_grm == content_grm], key=lambda x: x.gross_price)
                    if offer == offers_of_same_amount[0]:
                        unit, price_net, unit_quantity = offer.fs_unit(exclude_categories_from_loose_orders)
                        base_price = offer.gross_kgm_price
                        offer_name = offer.name
                        if base_price:
                            offer_name += f' ({price_str(base_price)}€/kg)'
                        if offer.shop == "b2b" and unit == "100g lose":
                            loose_offers_count += 1
                        article = foodsoft_article.Article(order_number=f'{offer.shop}_{offer.item_id}', name=offer_name, note=product.compose_note(), unit=unit, price_net=price_net, available=offer.available, vat=offer.vat, unit_quantity=unit_quantity, category=category.name, manufacturer=product.manufacturer, origin=product.origin, ignore=False, orig_unit=offer.orig_unit) # note=offer.description

                        self.articles.append(article)

                        if loose_offers_count > 0: # only import smallest loose B2B offer per product
                            break

        self.articles, self.notifications = foodsoft_article_import.rename_duplicates(locales=session.locales, articles=self.articles, notifications=self.notifications)

        self.log.append(base.LogEntry(action="webshop read", done_by=base.full_user_name(session)))
        self.next_possible_methods = [generate_csv]
        self.completion_percentage = 33

    def generate_csv(self, session):
        # TODO: test changes
        config = base.read_config(self.foodcoop, self.configuration)
        version_delimiter = "_v"
        articles_from_foodsoft, self.notifications = foodsoft_article_import.get_articles_from_foodsoft(locales=session.locales, supplier_id=self.supplier_id, foodsoft_connector=session.foodsoft_connector, notifications=self.notifications, version_delimiter=version_delimiter)
        self.articles, self.notifications = foodsoft_article_import.compare_manual_changes(locales=session.locales, foodcoop=self.foodcoop, supplier=self.configuration, articles=self.articles, articles_from_foodsoft=articles_from_foodsoft, version_delimiter=version_delimiter, notifications=self.notifications)
        self.articles = foodsoft_article_import.version_articles(articles=self.articles, articles_from_foodsoft=articles_from_foodsoft, version_delimiter=version_delimiter, compare_name=False)
        self.articles = sorted(self.articles, key=lambda x: x.name)
        self.notifiations = foodsoft_article_import.write_articles_csv(locales=session.locales, file_path=base.file_path(path=self.path, folder="download", file_name=self.configuration + "_Artikel_" + self.name), articles=self.articles, notifications=self.notifications)
        message = foodsoft_article_import.compose_articles_csv_message(locales=session.locales, supplier=self.configuration, foodsoft_url=session.settings.get('foodsoft_url'), supplier_id=self.supplier_id, categories=self.categories, ignored_categories=self.ignored_categories, ignored_subcategories=self.ignored_products, ignored_articles=self.ignored_articles, notifications=self.notifications, prefix=base.read_in_config(config, "message prefix", ""))
        base.write_txt(file_path=base.file_path(path=self.path, folder="display", file_name="Zusammenfassung"), content=message)

        self.log.append(base.LogEntry(action="CSV generated", done_by=base.full_user_name(session)))
        self.next_possible_methods = [mark_as_imported]
        self.completion_percentage = 67

    def mark_as_imported(self, session):
        base.set_config_detail(foodcoop=self.foodcoop, configuration=self.configuration, detail="last imported run", value=self.name)

        self.log.append(base.LogEntry(action="marked as imported", done_by=base.full_user_name(session)))
        self.next_possible_methods = []
        self.completion_percentage = 100

    def fetch_rss(self, driver):
        driver.get("https://www.fairfood.bio/feeds/google")
        rss_xml = driver.page_source
        return rss_xml

    def parse_articles(self, driver, config, xml, shop="b2c"):
        rss_articles = ET.fromstring(xml)
        ns = {'g': 'http://base.google.com/ns/1.0'}
        recipient_vat = vat.reduced(base.read_in_config(config, "country of destination"))
        original_vat = vat.reduced("de")
        for item in rss_articles.findall('./channel/item'):
            if item.find('g:availability', ns).text == "in stock":
                try:
                    product_type = item.find('g:product_type', ns).text
                except AttributeError:
                    product_type = "kein"
                if product_type in [c.name for c in self.categories]:
                    category = [c for c in self.categories if c.name == product_type][0]
                elif product_type in self.categories_to_ignore:
                    if not [c for c in self.ignored_categories if c.name == product_type]:
                        self.ignored_categories.append(base.Category(name=product_type))
                    continue
                else:
                    category = base.Category(name=product_type)
                    self.categories.append(category)
                name = item.find('title').text.replace("&amp;", "&").replace("gross", "groß").replace("Natur", "natur").replace("Geröstet", "geröstet").replace("Gesalzen", "gesalzen").replace("Süss-", "süß-").replace("Im ", "im ").replace(" Getrocknet &", "").replace(" getrocknet", "").replace(" Getrocknet", "").replace("Entsteint", "entsteint")
                orig_unit = item.find('g:unit_pricing_measure', ns).text.replace("none", "x").replace("eur", "Euro")
                price = float(item.find('g:price', ns).text.replace(" EUR", "").replace(",", ".").replace("&quot;", '"'))
                if shop == "b2c":
                    price = price / (1.0 + original_vat / 100) # calculating net price
                product_number = int(item.find('g:item_group_id', ns).text)
                if product_number in [p.number for p in category.subcategories]: # check only in category.subcategories
                    product = [p for p in category.subcategories if p.number == product_number][0]
                elif product_number in self.products_to_ignore:
                    if not [p for p in self.ignored_products if p.number == product_number]:
                        self.ignored_products.append(base.Category(number=product_number, name=name.split(" (")[0]))
                    continue
                else:
                    product = Product(number=product_number, name=name.split(" (")[0])
                    driver.get(item.find('link').text)
                    webpage = BeautifulSoup(driver.page_source, "lxml")
                    if webpage.body.find("h1", class_="font-headline text-4xl leading-none"):
                        ingredients_tag = webpage.body.find("p", class_="max-w-xs")
                        if ingredients_tag:
                            product.ingredients = ingredients_tag.get_text().replace("Zutaten:", "").strip()
                        info_list = webpage.body.find(class_="font-bold leading-loose my-2")
                        if product.ingredients and "Bio" not in product.ingredients and "Bio" in info_list.get_text():
                            product.ingredients += " (bio)"
                        origin_info = info_list.find_all(lambda tag: tag.name == "li" and ("Bio-Qualität aus " in tag.text or "Geerntet und getrocknet in " in tag.text or "Geknackt und verarbeitet in " in tag.text))
                        if origin_info:
                            product.origin = origin_info[0].text.replace("Bio-Qualität aus ", "").replace("Geerntet und getrocknet in ", "").replace("Geknackt und verarbeitet in ", "").replace("der ", "").replace("dem ", "").replace(", ", "/").replace(" und ", "/").strip()
                        else:
                            cooperative_links = [link for link in webpage.body.main.find_all("a", href=True) if "kooperative/" in link["href"]]
                            if cooperative_links:
                                product.origin = cooperative_links[0]["href"].split("/")[-1].capitalize().replace("Turkei", "Türkei").replace("Burkina-faso", "Burkina Faso").replace("Palastina", "Palästina").strip()
                    else:
                        print("Web page not valid for product " + str(product_number))
                        continue
                    if product_type == "Cashew-Käse":
                        product.manufacturer = "Udo Flachs Nóbrega, Cashewrella"
                        if product.origin:
                            product.origin += " / "
                        product.origin += "Göttingen"
                    elif product.origin == "Burkina Faso":
                        product.manufacturer = "Fairtrade-Kooperative Sookein"
                    elif product.origin == "China":
                        product.origin += " (Shandong)"
                        product.manufacturer = "Fairtrade-Kooperative"
                    elif product.origin == "Palästina":
                        product.manufacturer = "Fairtrade-Kooperative Canaan Palestine"
                    elif product.origin == "Tunesien":
                        product.manufacturer = "Fairtrade-Kooperative in Kebili"
                    elif product.origin == "Nigeria":
                        product.manufacturer = "Cashew for You, Okey Ugwu"
                    elif product.origin == "Kenia":
                        product.manufacturer = "Fair for Life Kooperative"
                    elif product.origin == "Tansania":
                        product.manufacturer = "Fairtrade-Kooperative / Kipepeo"
                    elif product.origin == "Türkei":
                        product.manufacturer = "Fairtrade-Projekt"
                    category.subcategories.append(product)
                item_id = item.find('g:id', ns).text
                if int(item_id) in self.articles_to_ignore:
                    if not [article for article in self.ignored_articles if article.order_number == int(item_id)]:
                        self.ignored_articles.append(foodsoft_article.Article(order_number=int(item_id), name=name, unit=orig_unit, price_net=price, vat=recipient_vat))
                    continue
                order_number = f'{shop}_{item_id}'
                if product_type in ["Nussmix", "Trockenfrüchte", "Nussmus", "Sparpakete", "Geschenke", "Schnelle Nussküche", "Haferdrink", "Cashew-Käse", "Nussige Schokocremes"]:
                    name = remove_prefix(name, product_type)
                name_split_at_braces = name.split(" (")
                if len(name_split_at_braces) > 1:
                    name = remove_suffix(name, f"({name_split_at_braces[0]})")
                description = item.find('description').text
                if description:
                    description = description.replace("&amp;", "&").replace("&quot;", '"')
                    if product_number == 55: # Nussmus im Viererpack
                        product.ingredients = description
                else:
                    description = ""
                if "Plesse Blue" in name:
                    product.note = "Blauschimmel-Alternative"
                elif "Vamembert" in name:
                    product.note = "Weichkäse-Alternative"
                elif "Crema" in name:
                    product.note = "Frischkäse-Alternative"
                elif "Cashewrella" in name:
                    product.note = "Mozzarella-Alternative"
                content = self.parse_unit_to_parcels(orig_unit)
                offer = Offer(shop=shop, item_id=item_id, name=name, content=content, orig_unit=orig_unit, price=price, vat=recipient_vat, description=description, category_name=category.name)
                product.offers.append(offer)

    def login(self, driver, email, password):
        driver.get("https://www.fairfood.bio/login")
        driver.find_element(By.ID, "email").send_keys(email)
        driver.find_element(By.ID, "password").send_keys(password)
        login_button = driver.find_element(By.XPATH, "//button[@type='submit']")
        login_button.click()

    def parse_unit_to_parcels(self, unit_string):
        unit_strings = unit_string.split("x")
        if len(unit_strings) == 2:
            multiplier = int(unit_strings[0].strip())
            if unit_strings[1]:
                content = self.parse_unit_to_parcels(unit_strings[1].strip())
            else:
                content = None
            return Parcel(content=content, amount=multiplier)
        elif len(unit_strings) == 1:
            if "kg" in unit_string:
                content_grm = int(float(unit_string.replace("kg", "").replace(",", ".").strip()) * 1000)
                return Parcel(content="grm", amount=content_grm)
            elif "g" in unit_string:
                content_grm = int(unit_string.replace("g", "").replace(",", ".").strip())
                return Parcel(content="grm", amount=content_grm)
            else:
                return None
        else:
            print("Unit parsing failed!")
            return None

    def parse_unit(self, unit_string):
        unit_strings = unit_string.split("x")
        if len(unit_strings) == 2:
            unit_quantity = int(unit_strings[0].strip())
            if unit_strings[1]:
                unit = unit_strings[1].strip()
            else:
                unit = "Stück"
        elif len(unit_strings) == 1:
            if "kg" in unit_string:
                content_kg = Decimal(unit_string.replace("kg", "").replace(",", ".").strip())
                unit_quantity = int(math.floor(content_kg * 10))
                unit = "100g lose"
            else:
                unit_quantity = 1
                unit = unit_string
        return unit, unit_quantity

class Product(base.Category):
    def __init__(self, number, name="", note="", origin="", manufacturer="", ingredients="", details="", offers=None):
        super().__init__(number=number, name=name)
        self.note = note
        self.origin = origin
        self.manufacturer = manufacturer
        self.ingredients = ingredients
        self.details = details
        if offers:
            self.offers = offers
        else:
            self.offers = []

    def compose_note(self):
        return ". ".join([string for string in [self.note, self.ingredients, self.details] if string != ""])

class Offer:
    def __init__(self, shop, item_id, name, content, orig_unit, price, vat, description=None, available=True, category_name=""):
        self.shop = shop
        self.item_id = item_id
        self.name = name
        self.content = content
        self.orig_unit = orig_unit
        self.available = available
        self.price = price
        self.vat = vat
        self.description = description
        self.category_name = category_name

    @property
    def content_grm(self):
        if self.content:
            return self.content.content_grm
        else:
            return 0

    @property
    def gross_price(self):
        return self.price + self.price * self.vat / 100

    @property
    def gross_kgm_price(self):
        content_grm = self.content_grm
        if content_grm == 0:
            return None
        else:
            return self.gross_price / (self.content_grm / 1000)

    def fs_unit(self, exclude_categories_from_loose_orders):
        unit_quantity = 1
        if self.content:
            if self.content.content == "grm":
                if self.content.amount > 1000 and self.category_name not in exclude_categories_from_loose_orders:
                    unit = "100g lose"
                    unit_quantity = int(self.content.amount / 100)
                    price = self.price / unit_quantity
                    self.name = self.name.split("(")[0] + "- lose"
                else:
                    unit = f"{self.content.amount}g"
                    price = self.price
                    if "Pfandglas" in self.name or (self.category_name in ["Nussmus", "Haferdrink", "Nussige Schokocremes"] and self.content.amount < 400):
                        unit += " MW-Glas"
                        self.name = self.name.split("(")[0] + "- Glas einzeln"
                    elif self.category_name != "Cashew-Käse":
                        if self.content.amount >= 2000:
                            self.name = self.name.split("(")[0] + "- Eimer"
                        else:
                            self.name = self.name.split("(")[0] + "- Beutel"
            elif self.content.content:
                unit = f"{self.content.content.amount}g"
                unit_quantity = self.content.amount
                price = self.price / unit_quantity
                if "Pfandglas" in self.name or self.category_name in ["Nussmus", "Haferdrink", "Nussige Schokocremes"]:
                    unit += " MW-Glas"
                    self.name = self.name.split("(")[0] + "- Glas"
            else:
                unit = self.orig_unit
                price = self.price
                self.name = self.name.split("(")[0]
        else:
            unit = self.orig_unit
            price = self.price
            self.name = self.name.split("(")[0]
        
        return unit, round(price, 2), unit_quantity # or: math.ceil(100.0 * float(price)) / 100.0

class Parcel:
    def __init__(self, content, amount=1):
        self.content = content
        self.amount = amount

    @property
    def content_grm(self):
        if self.content == "grm":
            return self.amount
        elif self.content:
            return self.amount * self.content.content_grm
        else:
            return 0

def price_str(price):
    rounded_price = round(price, 2)
    return ('%.2f' % rounded_price).replace(".", ",")

def remove_prefix(text, prefix):
    if text.startswith(prefix):
        text = text[len(prefix):].strip()
    return text

def remove_suffix(text, suffix):
    text = text.strip()
    if text.endswith(suffix):
        text = text[:(-1)*len(suffix)].strip()
    return text

if __name__ == "__main__":
    run = ScriptRun(foodcoop="Test coop", configuration="Test supplier")
    while run.next_possible_methods:
        func = getattr(run, run.next_possible_methods[0].name)
        func(session) # TODO: define session
    run.save()
