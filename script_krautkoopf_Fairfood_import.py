"""
Script for reading out the webshop from Fairfood Freiburg (screen-scraping) and creating a CSV file for article upload into Foodsoft.
"""

from bs4 import BeautifulSoup
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager
import re
import os
import math
import time
from decimal import *
# from difflib import SequenceMatcher

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
        base.Variable(name="read B2B shop only", required=False, example=False),
        base.Variable(name="country of destination", required=True, example="AT", description="country in which the goods will be delivered (important for VAT calculation)"),
        base.Variable(name="ignore categories by name (exact, case-sensitive)", required=False, example=["Dörr-Obst", "Brot/Gebäck"]),
        base.Variable(name="ignore categories by name (containing, case-insensitive)", required=False, example=["dörr", "bäck"]),
        base.Variable(name="ignore products by name (exact, case-sensitive)", required=False, example=["Birnennektar"]),
        base.Variable(name="ignore products by name (containing, case-insensitive)", required=False, example=["nektar"]),
        base.Variable(name="resort products in categories", required=False, example={"Kategorie 1": {"exact": False, "case-sensitive": False, "original categories": ["Obst & Gemüse", "Äpfel"], "target categories": {"Fruchtgemüse": ["Zucchini", "tomate"]}}}),
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
        self.read_B2B_shop_only = base.read_in_config(config, "read B2B shop only", False)
        self.categories_to_ignore_exact = config.get("ignore categories by name (exact, case-sensitive)", [])
        self.categories_to_ignore_containing = config.get("ignore categories by name (containing, case-insensitive)", [])
        self.products_to_ignore_exact = config.get("ignore products by name (exact, case-sensitive)", [])
        self.products_to_ignore_containing = config.get("ignore products by name (containing, case-insensitive)", [])
        self.resort_articles_in_categories = config.get("resort articles in categories", {})
        self.exclude_categories_from_loose_orders = base.read_in_config(config, "exclude categories from loose orders", [])

        self.categories = [] # like "Nüsse", "Nussmus" etc. with Products as subcategories // previously "product types" like "Cashewkerne", which have Products as subcategories (= "item groups" like "Cashewkerne Chili & Paprika")
        self.articles = [] # the selection of offers loaded into foodsoft
        self.ignored_categories = []
        self.ignored_products = []
        self.notifications = [] # notes for the run's info message
        self.recipient_vat_reduced = vat.reduced(base.read_in_config(config, "country of destination"))
        self.recipient_vat_standard = vat.standard(base.read_in_config(config, "country of destination"))
        self.original_vat_reduced = vat.reduced("de")
        self.original_vat_standard = vat.standard("de")

        driver = webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()))

        if email and password:
            self.login(driver=driver, email=email, password=password)
            self.read_shop(driver=driver, config=config, b2b=True)

        if not self.read_B2B_shop_only:
            self.read_shop(driver=driver, config=config) # B2C shop

        for category in self.categories:
            for product in category.subcategories:
                category_name = foodsoft_article_import.resort_articles_in_categories(article_name=product.name, category_name=category.name, resort_articles_in_categories=self.resort_articles_in_categories)
                offers = sorted(product.offers, key=lambda x: x.content_grm)
                loose_offers_count = 0
                for offer in offers:
                    content_grm = offer.content_grm
                    offers_of_same_amount = sorted([o for o in offers if o.content_grm == content_grm], key=lambda x: x.gross_price)
                    if offer == offers_of_same_amount[0]:
                        unit, price_net, unit_quantity = offer.fs_unit(self.exclude_categories_from_loose_orders)
                        base_price = offer.gross_kgm_price
                        offer_name = offer.name
                        if base_price:
                            offer_name += f' ({price_str(base_price)}€/kg)'
                        if unit == "100g lose": # offer.shop == "b2b" and 
                            loose_offers_count += 1
                        article = foodsoft_article.Article(order_number=f"{offer.shop}_{offer.number}", name=offer_name, note=product.compose_note(), unit=unit, price_net=price_net, available=offer.available, vat=offer.vat, deposit=offer.deposit, unit_quantity=unit_quantity, category=category_name, manufacturer=product.manufacturer, origin=product.origin, ignore=False, orig_unit=offer.orig_unit) # note=offer.description

                        self.articles.append(article)

                        if loose_offers_count > 0: # only import smallest loose offer per product
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
        message = foodsoft_article_import.compose_articles_csv_message(locales=session.locales, supplier=self.configuration, foodsoft_url=session.settings.get('foodsoft_url'), supplier_id=self.supplier_id, categories=self.categories, ignored_categories=self.ignored_categories, ignored_subcategories=self.ignored_products, notifications=self.notifications, prefix=base.read_in_config(config, "message prefix", ""))
        base.write_txt(file_path=base.file_path(path=self.path, folder="display", file_name="Zusammenfassung"), content=message)

        self.log.append(base.LogEntry(action="CSV generated", done_by=base.full_user_name(session)))
        self.next_possible_methods = [mark_as_imported]
        self.completion_percentage = 67

    def mark_as_imported(self, session):
        base.set_config_detail(foodcoop=self.foodcoop, configuration=self.configuration, detail="last imported run", value=self.name)

        self.log.append(base.LogEntry(action="marked as imported", done_by=base.full_user_name(session)))
        self.next_possible_methods = []
        self.completion_percentage = 100

    def login(self, driver, email, password):
        driver.get("https://b2b.fairfood.bio/account/login")
        time.sleep(1)
        driver.find_element(By.ID, "loginMail").send_keys(email)
        driver.find_element(By.ID, "loginPassword").send_keys(password)
        login_button = driver.find_element(By.XPATH, "//div[@class='login-submit']/button")
        login_button.click()

    def read_shop(self, driver, config, b2b=False):
        ignored_exceptions = (NoSuchElementException,)
        if b2b:
            shop = "b2b"
        else:
            shop = "b2c"
            driver.get(f"https://fairfood.bio")
        time.sleep(1)
        category_links = BeautifulSoup(driver.page_source, features="html.parser").body.find(class_="nav main-navigation-menu").find_all("a")
        category_links = [cl for cl in category_links if cl.get("title") not in ["Aktion", "Aktionen", "Alle Produkte", "Rezepte", "Unsere Mission"]]
        for cl in category_links:
            current_category = None
            category_name = cl.get("title")
            for c in self.categories:
                if c.name == category_name:
                    current_category = c
            if not current_category:
                current_category = base.Category(name=category_name)
                if base.equal_strings_check(list1=[category_name], list2=self.categories_to_ignore_exact, case_sensitive=True, strip=False) or base.containing_strings_check(list1=[category_name], list2=self.categories_to_ignore_containing, case_sensitive=False, strip=False):
                    if category_name not in [c.name for c in self.ignored_categories]:
                        self.ignored_categories.append(current_category)
                    continue
                else:
                    self.categories.append(current_category)
            page = 0
            products_found = True
            while products_found:
                page += 1
                driver.get(f"{cl.get('href')}?p={str(page)}")
                time.sleep(1)
                product_links = [p.get_attribute('href') for p in driver.find_elements(By.XPATH, "//a[@class='product-name']")]
                if not product_links:
                    products_found = False
                for product_link in product_links:
                    driver.get(product_link)
                    time.sleep(1)
                    # It seems all offers are displayed as separate products, hence we don't need to go through the offers. In case we have to do this, here's the code:
                    # driver.find_element(By.XPATH, "//div[@class='product-detail-configurator-option']/label").click() # go to first product option
                    # next_option = driver.find_element(By.XPATH, "//input[@class='product-detail-configurator-option-input is-combinable'][@checked='checked']/../following-sibling::div/label")
                    # next_option.click() # put this in a while next_option loop with try-except NoSuchElementException: break
                    try:
                        parent_id = driver.find_element(By.XPATH, "//input[@name='parentId']").get_attribute('value')
                    except NoSuchElementException:
                        try:
                            parent_id = driver.find_element(By.XPATH, "//form[@class='review-filter-form']").get_attribute('action').split("parentId=")[-1]
                        except NoSuchElementException:
                            parent_id = driver.find_element(By.XPATH, "//form[@class='product-detail-review-language-form']").get_attribute('action').split("parentId=")[-1]
                    current_product = None
                    for p in current_category.subcategories:
                        if p.number == parent_id:
                            current_product = p
                    name, orig_name, orig_unit = self.parse_product_name(driver=driver)
                    if not current_product:
                        origin = ""
                        origin_div = driver.find_element(By.XPATH, "//div[@class='col-md-6']/div")
                        if origin_div.get_attribute("textContent"):
                            origin_h = None
                            try:
                                origin_h = origin_div.find_element(By.CSS_SELECTOR, "h3")
                            except NoSuchElementException:
                                try:
                                    origin_h = origin_div.find_element(By.CSS_SELECTOR, "h2")
                                except NoSuchElementException:
                                    pass
                            if origin_h:
                                origin = origin_h.get_attribute("textContent")
                                if "aus " in origin:
                                    origin = origin.split("aus ")[1]
                                elif "aus " in origin:
                                    origin = origin.split("aus ")[1]
                                elif "in " in origin:
                                    origin = origin.split("in ")[1]
                                origin = origin.split("\n")[0].strip()
                        ingredients = driver.find_element(By.XPATH, "//div[@class='product-detail-description-text']").text.split("Zutaten:")[-1].split("\n")[0].replace("&nbsp", "").strip()
                        if ingredients == name:
                            ingredients = ""
                        current_product = Product(number=parent_id, name=name, origin=origin, ingredients=ingredients)
                        if base.equal_strings_check(list1=[orig_name, name], list2=self.products_to_ignore_exact, case_sensitive=True, strip=False) or base.containing_strings_check(list1=[orig_name, name], list2=self.products_to_ignore_containing, case_sensitive=False, strip=False):
                            if parent_id not in [ip.number for ip in self.ignored_products]:
                                self.ignored_products.append(current_product)
                            continue
                        else:
                            current_category.subcategories.append(current_product)
                    number = product_link.split("/")[-1]
                    if number not in [o.number for o in current_product.offers]:
                        self.parse_offer(driver=driver, current_product=current_product, current_category=current_category, orig_name=orig_name, orig_unit=orig_unit, shop=shop, number=number, b2b=b2b)
                    if not b2b: # in the B2C shop, there are some products with "hidden" options, so have to check if there any offers we haven't got yet
                        try:
                            options = driver.find_elements(By.XPATH, "//div[@class='product-detail-configurator-options']/div/label")
                        except NoSuchElementException:
                            continue
                        hidden_options = [opt for opt in [o.get_attribute("title") for o in options] if opt not in [of.orig_unit for of in current_product.offers]]
                        print(hidden_options)
                        for ho in hidden_options:
                            driver.find_element(By.XPATH, f"//div[@class='product-detail-configurator-options']/div/label[@title='{ho}']").click()
                            time.sleep(1)
                            number = driver.find_element(By.XPATH, "//meta[@property='og:url']").get_attribute('content').split("/")[-1]
                            name, orig_name, orig_unit = self.parse_product_name(driver=driver)
                            self.parse_offer(driver=driver, current_product=current_product, current_category=current_category, orig_name=orig_name, orig_unit=orig_unit, shop=shop, number=number, b2b=b2b)

    def parse_product_name(self, driver):
        orig_name = driver.find_element(By.XPATH, "//h1[@class='product-detail-name']").text
        name = orig_name.replace(" Fairtrade", "").replace("Bio ", "").replace("Bio-", "").replace("fair for life ", "").replace("Faires ", "").replace("Fairer ", "").replace("Faire ", "")
        if unit_match := re.search(r"\d*x?\d+(?:,\d+)?\s?k?g", name):
            orig_unit = unit_match.group(0)
            name = name.replace(orig_unit, "").strip()
        else:
            orig_unit = "Stück"
        return name, orig_name, orig_unit

    def parse_offer(self, driver, current_product, current_category, orig_name, orig_unit, shop, number, b2b):
        net_price = float(driver.find_element(By.XPATH, "//meta[@itemprop='price']").get_attribute('content'))
        reduced_vat = True
        if base.containing_strings_check(list1=[orig_name, current_product.name], list2=["kochbuch"], case_sensitive=False, strip=False) and orig_unit == "Stück":
            reduced_vat = False
        if reduced_vat:
            original_vat = self.original_vat_reduced
            recipient_vat = self.recipient_vat_reduced
        else:
            original_vat = self.original_vat_standard
            recipient_vat = self.recipient_vat_standard
        if not b2b:
            net_price = net_price / (1.0 + original_vat / 100) # calculating net price
        current_product.offers.append(Offer(shop=shop, number=number, name=current_product.name, content=self.parse_unit_to_parcels(orig_unit), orig_unit=orig_unit, price=net_price, vat=recipient_vat, category_name=current_category.name))
        # return current_product

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

class Product(base.Category):
    def __init__(self, number=None, name="", note="", origin="", manufacturer="", ingredients="", details="", offers=None):
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
    def __init__(self, shop, number, name, content, orig_unit, price, vat, description=None, available=True, category_name="", deposit=0):
        self.shop = shop
        self.number = number
        self.name = name
        self.content = content
        self.orig_unit = orig_unit
        self.available = available
        self.price = price
        self.vat = vat
        self.description = description
        self.category_name = category_name
        self.deposit = deposit

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
                    self.name = self.name.split("(")[0] + " - lose"
                else:
                    unit = f"{self.content.amount}g"
                    price = self.price
                    if self.content.amount < 400:
                        # unit += " MW-Glas"
                        self.name = self.name.split("(")[0] + " - MW-Glas einzeln"
                    else:
                        if self.content.amount >= 2000:
                            self.name = self.name.split("(")[0] + " - Eimer"
                            unit = self.orig_unit
                            self.deposit = 3
                        else:
                            self.name = self.name.split("(")[0] + " - Beutel"
                            # unit += " Beutel"
            elif self.content.content:
                unit = f"{self.content.content.amount}g"
                unit_quantity = self.content.amount
                price = self.price / unit_quantity
                if self.content.content.amount < 400:
                    # unit += " MW-Glas"
                    self.name = self.name.split("(")[0] + " - MW-Glas"
            else:
                unit = self.orig_unit
                price = self.price
                self.name = self.name.split("(")[0]
        else:
            if self.orig_unit == "1 x":
                unit = "Stück"
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

"""
def remove_prefix(text, prefix):
    if text.startswith(prefix):
        text = text[len(prefix):].strip()
    return text

def remove_suffix(text, suffix):
    text = text.strip()
    if text.endswith(suffix):
        text = text[:(-1)*len(suffix)].strip()
    return text
"""

if __name__ == "__main__":
    run = ScriptRun(foodcoop="Test coop", configuration="Test supplier")
    while run.next_possible_methods:
        func = getattr(run, run.next_possible_methods[0].name)
        func(session) # TODO: define session
    run.save()
