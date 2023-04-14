"""
Script for reading out the webshop of Biohof Müllner, A-7412 Wolfau and creating a CSV file for article upload into Foodsoft.

Sojabohnen im Glas: 320g /190g Abtropfgewicht
Hanföl kaltgepresst: gleiches Produkt 2x eingetragen
"""

import importlib
from bs4 import BeautifulSoup
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager
import re
import time

import base
import foodsoft_article
import foodsoft_article_import

# Inputs this script's methods take
# no inputs needed

# Executable script methods
read_webshop = base.ScriptMethod(name="read_webshop")
generate_csv = base.ScriptMethod(name="generate_csv")
mark_as_imported = base.ScriptMethod(name="mark_as_imported")

def config_variables(): # List of the special config variables this script uses, whether they are required and how they could look like
    return [
        base.Variable(name="Foodsoft supplier ID", required=False, example=12),
        base.Variable(name="last imported run", required=False),
        base.Variable(name="ignore categories by name (exact, case-sensitive)", required=False, example=["Dörr-Obst", "Brot/Gebäck"]),
        base.Variable(name="ignore categories by name (containing, case-insensitive)", required=False, example=["dörr", "bäck"]),
        base.Variable(name="ignore articles by name (exact, case-sensitive)", required=False, example=["Birnennektar"]),
        base.Variable(name="ignore articles by name (containing, case-insensitive)", required=False, example=["nektar"]),
        base.Variable(name="resort articles in categories", required=False, example={"Kategorie 1": {"exact": False, "case-sensitive": False, "original categories": ["Obst & Gemüse", "Äpfel"], "target categories": {"Fruchtgemüse": ["Zucchini", "tomate"]}}}),
        base.Variable(name="create loose offers", required=False, example={"all products": {"split amounts from": 5, "split amount into": 0.5}}) # of each product, the offer with the smallest amount >= 5 will be split into units of 0.5 (e.g. kg) and corresponding unit_quantity. Larger offers of the same product will be ignored. TODO: Filter for categories and/or articles
        ]

class ScriptRun(base.Run):
    def __init__(self, foodcoop, configuration):
        super().__init__(foodcoop=foodcoop, configuration=configuration)
        self.next_possible_methods = [read_webshop]

    def read_webshop(self, session):
        config = base.read_config(self.foodcoop, self.configuration)
        supplier_id = config.get("Foodsoft supplier ID")
        categories_to_ignore_exact = config.get("ignore categories by name (exact, case-sensitive)", [])
        categories_to_ignore_containing = config.get("ignore categories by name (containing, case-insensitive)", [])
        articles_to_ignore_exact = config.get("ignore articles by name (exact, case-sensitive)", [])
        articles_to_ignore_containing = config.get("ignore articles by name (containing, case-insensitive)", [])
        resort_articles_in_categories = config.get("resort articles in categories", {})
        create_loose_offers = config.get("create loose offers", {})

        self.articles = []
        self.categories = []
        self.ignored_articles = []
        self.ignored_categories = []
        self.notifications = []
        base_url = "https://www.biohofmuellner.at"

        driver = webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()))
        driver.get(base_url + "/shop")
        ignored_exceptions = (NoSuchElementException,StaleElementReferenceException,)
        accept_cookies = WebDriverWait(driver, 20, ignored_exceptions=ignored_exceptions).until(EC.element_to_be_clickable((By.XPATH, "//div[@class='_27MYo']/a")))
        accept_cookies.click()
        product_links = BeautifulSoup(driver.page_source, features="html.parser").body.find(class_="_1l7uY").find_all("a")
        for product_link in product_links:
            driver.get(base_url + product_link.get("href"))
            time.sleep(1)
            product_page = BeautifulSoup(driver.page_source, features="html.parser").body
            info = product_page.find(class_="_39RBN")
            orig_name = info.find("h1").text.replace("bio ", "").replace("Bio ", "")
            description = info.find("p").get_text()
            category_name = driver.find_element(By.XPATH, "//ul[@class='YSWQ4 _2ePf1']/li[2]/p/a/span").text
            category_name = foodsoft_article_import.resort_articles_in_categories(article_name=orig_name, category_name=category_name, resort_articles_in_categories=resort_articles_in_categories)
            category_found = False
            for c in self.categories + self.ignored_categories:
                if c.name == category_name:
                    cat = c
                    category_found = True
                    break
            if not category_found:
                cat = base.Category(name=category_name)
                if base.equal_strings_check(list1=[category_name], list2=categories_to_ignore_exact, case_sensitive=True, strip=False) or base.containing_strings_check(list1=[category_name], list2=categories_to_ignore_containing, case_sensitive=False, strip=False):
                    self.ignored_categories.append(cat)
                    continue
                else:
                    self.categories.append(cat)
            elif cat in self.ignored_categories:
                continue
            product = base.Category(name=orig_name)
            product.articles = []
            product.open = True
            cat.subcategories.append(product)

            select_box_bs = product_page.find(class_="_1Qhy3")
            if select_box_bs:
                options = select_box_bs.find_all("option")
                for option in options:
                    if option.has_attr("hidden") or option.has_attr("disabled"):
                        continue
                    option_contents = option.get_text().replace("\xa0", " ").split(" - ")
                    unit = option_contents[0].split(" (")[0]
                    price = float(option_contents[1].split(" ")[0].replace(",", "."))
                    order_number = f"{orig_name}_{unit}" # unit incl. unit quanitity here, can be e.g. "8 x 250 ml"
                    if "x" in unit:
                        unit_strings = unit.split("x")
                        unit_quantity = int(unit_strings[0].strip())
                        unit = unit_strings[1].strip()
                        price = round(price / unit_quantity, 2)
                    else:
                        unit_quantity = 1
                    unit_re = re.search(r"(\d+(?:,\d+)?)\s(\D*)", unit)
                    amount = float(unit_re.group(1).replace(",", "."))
                    base_unit = unit_re.group(2).strip()
                    if base_unit == "g":
                        amount /= 1000
                        base_unit = "kg"
                    elif base_unit == "ml":
                        amount /= 1000
                        base_unit = "l"
                    elif base_unit not in ["kg", "l"]:
                        if amount == 1:
                            unit = base_unit
                        base_unit = None
                    if base_unit:
                        base_price = price / amount
                        name = f"{orig_name} ({foodsoft_article_import.base_price_str(base_price, base_unit)})"
                    else:
                        name = orig_name
                    article = foodsoft_article.Article(order_number=order_number, name=name, unit=unit, unit_quantity=unit_quantity, price_net=price, category=category_name, origin="eigen", note=description, amount=amount, base_unit=base_unit, orig_name=orig_name)
                    product.articles.append(article)
            else:
                price = float(product_page.find(class_="P9xMj").get_text().replace("\xa0", " ").split(" ")[0].replace(",", "."))
                article = foodsoft_article.Article(order_number=orig_name, name=orig_name, unit="Stk", price_net=price, category=category_name, origin="eigen", note=description, amount=None, base_unit=None, orig_name=orig_name)
                product.articles.append(article)

        for c in self.categories:
            for p in c.subcategories:
                p.articles = sorted(p.articles, key=lambda x: x.amount)
                for article in p.articles:
                    other_articles = [a for a in p.articles if a != article]
                    if article.unit in [a.unit for a in other_articles]:
                        if article.unit_quantity == 1:
                            article.name += " einzeln"
                        # else:
                        #     article.name += " im Gebinde"
                    article_to_ignore = False
                    if article.base_unit:
                        for subdict in create_loose_offers:
                            if article.amount >= create_loose_offers[subdict].get("split amounts from") and create_loose_offers[subdict].get("split amount into"):
                                if p.open:
                                    divisor = round(article.amount / create_loose_offers[subdict].get("split amount into"))
                                    article.amount /= divisor
                                    article.unit = f'{str(article.amount).replace(".", ",")} {article.base_unit} lose'
                                    article.price_net = round(article.price_net / divisor, 2)
                                    article.unit_quantity *= divisor
                                    p.open = False
                                else:
                                    article_to_ignore = True
                    if base.equal_strings_check(list1=[article.orig_name, article.order_number], list2=articles_to_ignore_exact, case_sensitive=True, strip=False) or base.containing_strings_check(list1=[article.orig_name, article.order_number], list2=articles_to_ignore_containing, case_sensitive=False, strip=False) or article_to_ignore:
                        self.ignored_articles.append(article)
                    else:
                        self.articles.append(article)

        driver.quit()

        self.articles, self.notifications = foodsoft_article_import.rename_duplicates(locales=session.locales, articles=self.articles, notifications=self.notifications, compare_unit=True, keep_full_duplicates=False)
        self.articles, self.notifications = foodsoft_article_import.rename_duplicate_order_numbers(locales=session.locales, articles=self.articles, notifications=self.notifications)

        self.next_possible_methods = [generate_csv]
        self.completion_percentage = 33
        self.log.append(base.LogEntry(action="webshop read", done_by=base.full_user_name(session)))

    def generate_csv(self, session):
        config = base.read_config(self.foodcoop, self.configuration)
        supplier_id = base.read_in_config(config, "Foodsoft supplier ID", None)
        articles_from_foodsoft, self.notifications = foodsoft_article_import.get_articles_from_foodsoft(locales=session.locales, supplier_id=supplier_id, foodsoft_connector=session.foodsoft_connector, notifications=self.notifications)
        self.articles, self.notifications = foodsoft_article_import.compare_manual_changes(locales=session.locales, foodcoop=self.foodcoop, supplier=self.configuration, articles=self.articles, articles_from_foodsoft=articles_from_foodsoft, notifications=self.notifications)
        self.notifications = foodsoft_article_import.write_articles_csv(locales=session.locales, file_path=base.file_path(path=self.path, folder="download", file_name=self.configuration + "_Artikel_" + self.name), articles=self.articles, notifications=self.notifications)
        message_prefix = config.get("message prefix", "")
        message = foodsoft_article_import.compose_articles_csv_message(locales=session.locales, supplier=self.configuration, foodsoft_url=session.settings.get('foodsoft_url'), supplier_id=supplier_id, categories=self.categories, ignored_categories=self.ignored_categories, ignored_articles=self.ignored_articles, notifications=self.notifications, prefix=message_prefix)
        base.write_txt(file_path=base.file_path(path=self.path, folder="display", file_name="Zusammenfassung"), content=message)

        self.log.append(base.LogEntry(action="CSV generated", done_by=base.full_user_name(session)))
        self.next_possible_methods = [mark_as_imported]
        self.completion_percentage = 67

    def mark_as_imported(self, session):
        base.set_config_detail(foodcoop=self.foodcoop, configuration=self.configuration, detail="last imported run", value=self.name)

        self.next_possible_methods = []
        self.completion_percentage = 100
        self.log.append(base.LogEntry(action="marked as imported", done_by=base.full_user_name(session)))

if __name__ == "__main__":
    importlib.invalidate_caches()
    script = importlib.import_module("script_krautkoopf_Renner_import") # I don't know why we have to do this, but if the ScriptRun object is just initialized directly (run = ScriptRun(...)), then it doesn't load when we try to load in web ("AttributeError: Can't get attribute 'ScriptRun' on <module '__main__' from 'web.py'>")
    run = script.ScriptRun(foodcoop="krautkoopf", configuration="Supplier X")
    while run.next_possible_methods:
        func = getattr(run, run.next_possible_methods[0].name)
        func()
    run.save()
