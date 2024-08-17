#This should work as an object API to connect with foodsoft and
#work with it.

import logging
import requests
import os
import re
from bs4 import BeautifulSoup as bs
import urllib.request
import copy
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager

import base
import script_libs.generic.foodsoft_article as foodsoft_article

logging.basicConfig() # level=logging.DEBUG

class Supplier:
    def __init__(self, no, name, address="", website="", origin="", category="", additional_fields=None, deleted=False, latitude=None, longitude=None, icon=None, icon_prefix=None, icon_color=None):
        self.no = no # ID from Foodsoft
        self.name = name
        self.address = address
        self.website = website
        self.origin = origin
        self.category = category
        self.additional_fields = additional_fields
        self.deleted = deleted
        self.latitude = latitude
        self.longitude = longitude
        self.icon = icon
        self.icon_prefix = icon_prefix
        self.icon_color = icon_color

    def apply_supplier_delimiters(self, supplier_name_prefix_delimiters, supplier_name_suffix_delimiters, category_name_prefix_delimiters, category_name_suffix_delimiters):
        for d in supplier_name_prefix_delimiters:
            self.name = self.name.split(d)[-1]
        for d in supplier_name_suffix_delimiters:
            self.name = self.name.split(d)[0]
        for d in category_name_prefix_delimiters:
            self.category = self.category.split(d)[-1]
        for d in category_name_suffix_delimiters:
            self.category = self.category.split(d)[0]

def read_foodsoft_config():
    foodcoop = "unnamed foodcoop"
    foodsoft_url = None
    if 'LS_FOODSOFT_URL' in os.environ:
        foodsoft_url = os.environ['LS_FOODSOFT_URL']
        foodcoop_list = re.split(".*/(.*)/", foodsoft_url)
        if len(foodcoop_list) < 2:
            logging.error("Could not extract foodcoop name from url " + foodsoft_url)
        else:
            foodcoop = foodcoop_list[1]
    foodsoft_user = None
    foodsoft_password = None
    if 'LS_FOODSOFT_USER' in os.environ and 'LS_FOODSOFT_PASS' in os.environ:
        foodsoft_user = os.environ['LS_FOODSOFT_USER']
        foodsoft_password = os.environ['LS_FOODSOFT_PASS']
    return foodcoop, foodsoft_url, foodsoft_user, foodsoft_password

class FSConnector:
    def __init__(self, url: str, user: str, password: str):
        self._session = None
        if not url.endswith("/"):
            url += "/"
        self._url = url
        self._url_login_request = url + 'login'
        self._url_login_post = url + 'sessions'

        self._default_header = {
                'Host': 'app.foodcoops.at',
                'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:69.0) Gecko/20100101 Firefox/69.0',
                'Content-Type':'application/x-www-form-urlencoded',
                'Upgrade-Insecure-Requests':'1'
                }

        self._login_data = {
                "utf8":"✓",
                'commit' : 'Anmelden'
                }

        self.login(user, password)

    def _get(self, url, header, response=None):
        while response is None: # TODO: max retries instead of endless loop?
            try:
                response = self._session.get(url, headers=header)
            except requests.exceptions.ConnectionError:
                print("requests.exceptions.ConnectionError, waiting 3 seconds and trying again ...")
                time.sleep(3)
        if response.status_code != 200: # TODO: I think we should handle errors instead of automatically closing the session & raising an error (also applies to _post function)
            self._session.close()
            logging.error('ERROR ' + str(response.status_code) + ' during GET ' + url)
            raise ConnectionError('Cannot get: ' +url)

        return response

    def _get_auth_token(self, request_content):
        if request_content is None:
            logging.error('ERROR failed to fetch authenticity_token')
            return ''
#        html = bs(response.content, 'html.parser')
#        auth_token =  html.find(attrs={'name':'authenticity_token'})
#        return auth_token['value']
        return bs(request_content, 'html.parser').find(attrs={'name':'authenticity_token'})['value']

    def _post(self, url, header, data, request):
        data['authenticity_token'] = self._get_auth_token(request.content)
        response = self._session.post(url, headers=header, data=data, cookies=request.cookies)
        if response.status_code != 200: #302
            logging.error('Error ' + str(response.status_code) + ' during POST ' + url)
            raise ConnectionError('Error cannot post to ' + url)

        return response

    def login(self, user, password):
        self._user = user
        self._login_data['nick'] = user
        self._login_data['password'] = password # TODO: don't save in object?

        login_header = self._default_header

        self._session = requests.Session()
        request = self._get(self._url_login_request, login_header)

        login_header['Referer'] = self._url_login_request

        response = self._post(self._url_login_post, login_header, self._login_data, request)
        # TODO: check if the login was really successful or not (due to false login data), for example by checking status codes?
        # If not, set self._session back to None, or store logged-in status in a boolean variable
        logging.debug(user + ' logged in successfully to ' + self._url)

    def logout(self):
        self._session.close()

    def open_driver(self):
        driver = webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()))
        driver.get(self._url)
        for cookie in self._session.cookies:
            driver.add_cookie({
                'name': cookie.name,
                'value': cookie.value,
                'path': cookie.path,
                'expiry': cookie.expires,
            })
        return driver

    def add_user_data(self, first_name=True, last_name=True, nick=False, workgroups=False, ordergroup=False):
        """
        Adds the requested data of the logged-in user to the FSConnector object:
        .user : ID of user
        .first_name
        .last_name
        .nick (None if nicknames are disabled in the Foodsoft instance)
        .workgroups : IDs of work groups which the user is member of, for example [1, 3, 11] or []
        .ordergroup : ID of the user's ordergroup
        """

        userdata_url = f"{self._url}home/profile"
        parsed_html = bs(self._get(userdata_url, self._default_header).content, 'html.parser')
        first_name_field = parsed_html.body.find(id="user_first_name")
        if not first_name_field:
            self._session.close()
            self._session = None
        else:
            self.user = int(parsed_html.body.find(class_="simple_form form-horizontal edit_user").get("id").split("edit_user_")[-1])
            if first_name:
                self.first_name = first_name_field.get("value")
            if last_name:
                self.last_name = parsed_html.body.find(id="user_last_name").get("value")
            if nick:
                nick_tag = parsed_html.body.find(id="user_nick")
                if nick_tag:
                    self.nick = nick_tag.get("value")
                else:
                    self.nick = None
            if workgroups:
                wg_links = parsed_html.body.select("[rel='nofollow']")
                self.workgroups = [int(link["href"].split("=")[-1]) for link in wg_links]
            if ordergroup:
                links = parsed_html.body.find_all("a")
                self.ordergroup = None
                for link in links:
                    href = link.get("href")
                    if href:
                        if "invites" in href:
                            self.ordergroup = int(href.split("=")[-1])
                            break
        
    def get_articles_CSV(self, supplier_id):
        supplier_url = f"{self._url}suppliers/{str(supplier_id)}/articles.csv"
        request = self._get(supplier_url, self._default_header)
        decoded_content = request.content.decode('utf-8')
        return decoded_content

    def get_supplier_data(self, name_fields=None, origin_fields=None, address_fields=None, website_fields=None, category_fields=None, additional_fields=None, exclude_categories=None):
        suppliers = []
        supplier_ids = []
        supplier_list_url = f"{self._url}suppliers"
        parsed_html = bs(self._get(supplier_list_url, self._default_header).content, 'html.parser')
        for row in parsed_html.body.find("tbody").find_all("tr"):
            supplier_ids.append(row.find_all("td")[0].find("a").get("href").split("suppliers/")[-1])
        for supplier_id in supplier_ids:
            supplier = self.get_data_of_supplier(supplier_id=supplier_id, name_fields=name_fields, origin_fields=origin_fields, address_fields=address_fields, website_fields=website_fields, category_fields=category_fields, additional_fields=copy.deepcopy(additional_fields), exclude_categories=exclude_categories)
            if supplier:
                suppliers.append(supplier)

        return suppliers

    def get_data_of_supplier(self, supplier_id, name_fields=None, origin_fields=None, address_fields=None, website_fields=None, category_fields=None, additional_fields=None, exclude_categories=None):
        supplier_url = f"{self._url}suppliers/{str(supplier_id)}/edit"
        parsed_html_body = bs(self._get(supplier_url, self._default_header).content, 'html.parser').body
        category = None
        if category_fields:
            for field in category_fields:
                category = parsed_html_body.find(id=f"supplier_{field}").select_one('option:checked').text # rewrite so it doesn't crash if no category selected
                if category:
                    if exclude_categories:
                        if category in exclude_categories:
                            return None
                    break
        fs_name = self.get_supplier_field_data(parsed_html_body=parsed_html_body, fields=["name"])
        if " †" in fs_name:
            deleted = True
        else:
            deleted = False
        name = self.get_supplier_field_data(parsed_html_body=parsed_html_body, fields=name_fields).replace(" †", "")
        address = self.get_supplier_field_data(parsed_html_body=parsed_html_body, fields=address_fields)
        origin = self.get_supplier_field_data(parsed_html_body=parsed_html_body, fields=origin_fields)
        website = self.get_supplier_field_data(parsed_html_body=parsed_html_body, fields=website_fields)
        if additional_fields:
            for af in additional_fields:
                value = self.get_supplier_field_data(parsed_html_body=parsed_html_body, fields=af.get("foodsoft field(s)"))
                if value:
                    af["value"] = value

        print(f"{name}: {additional_fields}")
        return Supplier(no=supplier_id, name=name, address=address, origin=origin, website=website, category=category, additional_fields=additional_fields, deleted=deleted)

    def get_supplier_field_data(self, parsed_html_body, fields):
        # checks each field in a list of fields for data and returns the first non-null value
        if fields:
            for field in fields:
                field = parsed_html_body.find(id=f"supplier_{field}")
                if field.name == "textarea":
                    field_value = field.text[1:] #get("value")
                else:
                    field_value = field.get("value")
                if field_value:
                    return field_value

    def get_stock_articles_and_suppliers(self, skip_unavailable_articles=False, suppliers=None, name_fields=None, origin_fields=None, address_fields=None, website_fields=None, category_fields=None, additional_fields=None, exclude_categories=None):
        """
        Returns a list of foodsoft_article.StockArticle objects.
        Stock quantity changes not included yet.
        """
        if not suppliers:
            suppliers = []
        parsed_html_body = bs(self._get(f"{self._url}stock_articles", self._default_header).content, 'html.parser').body
        rows = parsed_html_body.find(id="articles-tbody").find_all("tr")
        stock_articles = []
        for row in rows:
            classes = row.get("class")
            if classes and classes[-1] == "unavailable":
                if skip_unavailable_articles:
                    continue
                else:
                    available = False
            else:
                available = True
            no = row.get("id").split("-")[-1]
            columns = row.find_all("td")
            category = columns[8].text
            if category in exclude_categories:
                continue
            name = columns[0].find("a").text
            in_stock = float(columns[1].text.replace(",", "."))
            ordered = float(columns[2].text.replace(",", "."))
            available = float(columns[3].text.replace(",", "."))
            unit = columns[4].text
            price_net = float(columns[5].text.replace(",", ".").replace("€", "").strip())
            vat = float(columns[6].text.replace(",", ".").replace("%", "").strip())
            supplier_id = columns[7].find("a").get("href").split("/")[-1]
            supplier = next((s for s in suppliers if s.no == supplier_id))
            if not supplier:
                supplier = self.get_data_of_supplier(supplier_id=supplier_id, name_fields=name_fields, origin_fields=origin_fields, address_fields=address_fields, website_fields=website_fields, category_fields=category_fields, additional_fields=additional_fields)
                if supplier:
                    suppliers.append(supplier)
            article_details_page = bs(self._get(f"{self._url}stock_articles/{no}", self._default_header).content, 'html.parser').body
            details_dl = article_details_page.find(id="stockArticleDetails").find("dl")
            deposit = float(details_dl.find_all("dd")[5].text.replace(",", ".").replace("€", "").strip())
            note = details_dl.find_all("dd")[8].text
            stock_articles.append(foodsoft_article.StockArticle(no=no, in_stock=in_stock, ordered=ordered, supplier=supplier, name=name, unit=unit, price_net=price_net, available=available, order_number=f"00_{str(no)}", note=note, vat=vat, deposit=deposit))
        return stock_articles, suppliers

    def get_article_categories(self):
        """
        Returns a list of base.Category objects.
        """
        parsed_html_body = bs(self._get(f"{self._url}article_categories", self._default_header).content, 'html.parser').body
        rows = parsed_html_body.find("tbody").find_all("tr")
        article_categories = []
        for row in rows:
            name = row.find("td").text
            number = row.find_all("td")[2].find("a").get("href").split("/")[-2]
            category = base.Category(name=name, number=number)
            category.keywords = []
            description = row.find_all("td")[1].text
            if description:
                if description.endswith("..."):
                    edit_body = bs(self._get(f"{self._url}article_categories/{number}/edit", self._default_header).content, 'html.parser').body
                    description = edit_body.find(id="article_category_description").text
                category.keywords = [kw.strip() for kw in description.split(",")]
            article_categories.append(category)
        return article_categories
