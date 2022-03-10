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
        base.Variable(name="last imported CSV", required=False, example="2021-10-27_1"),
        base.Variable(name="VAT on B2B articles", required=False, example=7, description="in percent"),
        base.Variable(name="categories to ignore", required=False, example=[2, 3, 9]),
        base.Variable(name="subcategories to ignore", required=False, example=[3, 51]),
        base.Variable(name="articles to ignore", required=False, example=[24245, 23953]),
        base.Variable(name="message prefix", required=False, example="Hallo"),
        base.Variable(name="discount percentage", required=False, example=5)
        ]

class ScriptRun(base.Run):
    def __init__(self, foodcoop, configuration):
        super().__init__(foodcoop=foodcoop, configuration=configuration)
        self.next_possible_methods = [read_webshop]
        self._session = None

    def read_webshop(self, session, email="", password=""):
        config = base.read_config(self.foodcoop, self.configuration)
        global supplier_id
        supplier_id = base.read_in_config(config, "Foodsoft supplier ID", None)
        global categories_to_ignore
        categories_to_ignore = base.read_in_config(config, "categories to ignore", [])
        global subcategories_to_ignore
        subcategories_to_ignore = base.read_in_config(config, "subcategories to ignore", [])
        global articles_to_ignore
        articles_to_ignore = base.read_in_config(config, "articles to ignore", [])

        self.articles = []
        self.notifications = []

        driver = webdriver.Firefox(executable_path=GeckoDriverManager().install()) #Change here if you want use Chromium

        #get B2C prices
        b2c_xml = self.fetch_rss(driver=driver)
        self.parse_articles(config, b2c_xml)

        if email and password:
            self.login(driver=driver, email=email, password=password)
            #after login get B2B prices
            b2b_xml = self.fetch_rss(driver=driver)
            self.parse_articles(config, b2b_xml, excl_vat=True)

        # TODO: filter articles, remove B2C offers when B2B offer is available, make selection of articles that should be displayed, check for duplicates, subtract discount percentage

        self.log.append(base.LogEntry(action="webshop read", done_by=base.full_user_name(session)))
        self.next_possible_methods = [generate_csv]
        self.completion_percentage = 33

    def generate_csv(self, session):
        # TODO: compare manual changes
        foodsoft_article_import.write_articles_csv(file_path=base.file_path(path=self.path, folder="download", file_name=self.configuration + "_Artikel_" + self.name), articles=self.articles, notifications=self.notifications)

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

    def parse_articles(self, config, xml, excl_vat=False):
        rss_articles = ET.fromstring(xml)
        ns = {'g': 'http://base.google.com/ns/1.0'}
        if excl_vat:
            vat = base.read_in_config(config, "VAT on B2B articles", 0)
        else:
            vat = 0
        for item in rss_articles.findall('./channel/item'):
            # Get the value from the attribute 'name'
            order_number = item.find('g:item_group_id', ns).text + "_" + item.find('g:id', ns).text
            name = item.find('title').text.replace("&amp;", "&")
            price = item.find('g:price', ns).text.replace(" EUR", "").replace(",", ".").replace("&quot;", '"')
            description = item.find('description').text
            if description:
                description = description.replace("&amp;", "&").replace("&quot;", '"')
            orig_unit = item.find('g:unit_pricing_measure', ns).text
            unit, unit_quantity = self.parse_unit(orig_unit) # TODO: add packaging to amount (e.g. 133g MW-Glas)
            price = math.ceil(100.0 * float(price) / float(unit_quantity)) / 100.0
            if item.find('g:availability', ns).text == "in stock":
                available = True
            else:
                available = False

            self.articles.append(foodsoft_article.Article(order_number=order_number, name=name, note=description, unit=unit, price_net=price, available=available, vat=vat, unit_quantity=unit_quantity, category="", manufacturer="", origin="", ignore=False, orig_unit=""))

    def login(self, driver, email, password):
        driver.get("https://www.fairfood.bio/login")
        driver.find_element(By.ID, "email").send_keys(email)
        driver.find_element(By.ID, "password").send_keys(password)
        login_button = driver.find_element(By.XPATH, "//button[@type='submit']")
        login_button.click()
        
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

if __name__ == "__main__":
    run = ScriptRun(foodcoop="Test coop", configuration="Test supplier")
    while run.next_possible_methods:
        func = getattr(run, run.next_possible_methods[0].name)
        func(session) # TODO: define session
    run.save()
