from bs4 import BeautifulSoup
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
import xml.etree.ElementTree as ET
import re
import os

import base
import foodsoft_article

# Inputs this script's methods take
# no inputs taken

# Executable script methods
generate_csv = base.ScriptMethod(name="generate_csv")
set_as_imported = base.ScriptMethod(name="set_as_imported")

def config_variables(): # List of the special config variables this script uses, whether they are required and how they could look like
    return [
        base.Variable(name="Foodsoft supplier ID", required=False, example=12),
        base.Variable(name="last imported CSV", required=False, example="2021-10-27_1"),
        base.Variable(name="categories to ignore", required=False, example=[2, 3, 9]),
        base.Variable(name="subcategories to ignore", required=False, example=[3, 51]),
        base.Variable(name="articles to ignore", required=False, example=[24245, 23953]),
        base.Variable(name="message prefix", required=False, example="Hallo"),
        base.Variable(name="discount percentage", required=False, example=5)
        ]

# TODO: environment variables no longer supported!
# def environment_variables(): # List of the special environment variables this script uses, whether they are required and how they could look like
#     return [
#         base.Variable(name="LS_FOODSOFT_URL", required=False, example="https://app.foodcoops.at/coop_xy/"),
#         base.Variable(name="LS_FOODSOFT_URL", required=False, example="name@foobar.com"),
#         base.Variable(name="LS_FOODSOFT_PASS", required=False, example="asdf1234"),
#         base.Variable(name="LS_FAIRFOOD_USER", required=True, example="name@foobar.com"),
#         base.Variable(name="LS_FAIRFOOD_PASS", required=True, example="asdf1234")
#         ]

class ScriptRun(base.Run):
    def __init__(self, foodcoop, configuration, started_by):
        super().__init__(foodcoop=foodcoop, configuration=configuration, started_by=started_by)
        self.next_possible_methods = [generate_csv]
        self._session = None
        self._driver = webdriver.Firefox() #Change here if you want use Chromium

    def fetch_rss(self):
        self._driver.get("https://www.fairfood.bio/feeds/google")
        rss_xml = driver.page_source
        return rss_xml

    def parse_articles(self, xml):
        rss_articles = ET.fromstring(xml).getroot()
        ns = {'g': 'http://base.google.com/ns/1.0'}
        for item in rss_articles.findall('./channel/item'):
            # Get the value from the attribute 'name'
            order_number = item.find('id', ns).text
            name = item.find('title').text
            price = item.find('g:price', ns).text
            description = item.find('description').text
            unit = item.find('g:unit_pricing_measure', ns).text
            #print(f'name: {name}, price: {price}, unit: {unit}, desription: {description}')

            #foodsoft_article.Article(order_number=orer_number, name=name, note=description, unit=TODO, price_net=TODO, category=TODO, manufacturer=TODO, origin=TODO, ignore=ignore, orig_unit=TODO)


    def generate_csv(self, session):
        config = base.read_config(self.foodcoop, self.configuration)
        global supplier_id
        supplier_id = base.read_in_config(config, "Foodsoft supplier ID", None)
        global categories_to_ignore
        categories_to_ignore = base.read_in_config(config, "categories to ignore", [])
        global subcategories_to_ignore
        subcategories_to_ignore = base.read_in_config(config, "subcategories to ignore", [])
        global articles_to_ignore
        articles_to_ignore = base.read_in_config(config, "articles to ignore", [])

        username = os.environ['LS_FAIRFOOD_USER']
        password = os.environ['LS_FAIRFOOD_PASS']

        #get B2C prices
        b2c_xml = self.fetch_rss()
        #self.parse_articles(b2c_xml)

        self.login(username, password)
        #after login get B2B prices
        b2b_xml = self.fetch_rss()
        self.parse_articles(b2b_xml)

        self.next_possible_methods = []


    def login(self, username, password):
        self._driver.get("https://www.fairfood.bio/login")
        self._driver.find_element(By.ID, "email").send_keys("username")
        self._driver.find_element(By.ID, "password").send_keys("password")
        login_button = self._driver.find_element(By.XPATH, "//button[@type='submit']")
        login_button.click()
        


        # articles = []
        # overlong_note = "This is a very long text. Since Foodsoft only supports up to 255 characters in the articles' data strings (note, manufacturer, origin) and won't validate them by itself, we have to resize it in order to not cause an error. Nobody would read it anyway to the end!"
        # test = base.Article(available=False, order_number=1, name="Test article", note=overlong_note, unit="1 kg", price_net=5.40, category="Test")
        # articles.append(test)

        # notifications = base.write_articles_csv(file_path=base.file_path(path=self.path, folder="download", file_name=self.configuration + "_articles_" + self.name), articles=articles)
        # test = base.write_articles_csv(file_path=base.file_path(path=self.path, folder="download", file_name=self.configuration + "_test_" + self.name), articles=articles)
        # base.write_txt(file_path=base.file_path(path=self.path, folder="display", file_name="Summary"), content=base.compose_articles_csv_message(supplier=self.configuration, notifications=notifications))
        # base.write_txt(file_path=base.file_path(path=self.path, folder="details", file_name="Log"), content="")
        # self.next_possible_methods = [set_as_imported]
        # self.completion_percentage = 80

    def set_as_imported(self, session):
        self.next_possible_methods = []
        self.completion_percentage = 100

if __name__ == "__main__":
    run = ScriptRun(foodcoop="Test coop", configuration="Test supplier", started_by="Test user")
    while run.next_possible_methods:
        func = getattr(run, run.next_possible_methods[0].name)
        func()
    run.save()
