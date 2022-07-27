#This should work as an object API to connect with foodsoft and
#work with it.

import logging
import requests
import os
import re
from bs4 import BeautifulSoup as bs
import urllib.request

logging.basicConfig(level=logging.DEBUG)

class Supplier:
    def __init__(self, name, address, description="", category="", custom_fields=None, latitude=None, longitude=None, icon=None, icon_prefix=None, icon_color=None):
        self.name = name
        self.address = address
        self.description = description
        self.category = category
        self.custom_fields = custom_fields
        self.latitude = latitude
        self.longitude = longitude
        self.icon = icon
        self.icon_prefix = icon_prefix
        self.icon_color = icon_color

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

    def _get(self, url, header, data=None):
        if data is None:
            response = self._session.get(url, headers=header)
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
        self._login_data['password'] = password

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

    def add_user_data(self, first_name=True, last_name=True, nick=False, workgroups=False, ordergroup=False):
        """
        Adds the requested data of the logged-in user to the FSConnector object:
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

    def get_supplier_data(self, custom_fields=None, exclude_categories=None):
        suppliers = []
        supplier_ids = []
        supplier_list_url = f"{self._url}suppliers"
        parsed_html = bs(self._get(supplier_list_url, self._default_header).content, 'html.parser')
        for row in parsed_html.body.find("tbody").find_all("tr"):
            supplier_ids.append(row.find_all("td")[0].find("a").get("href").split("suppliers/")[-1])
        for supplier_id in supplier_ids:
            supplier = self.get_data_of_supplier(supplier_id=supplier_id, custom_fields=custom_fields, exclude_categories=exclude_categories)
            if supplier:
                suppliers.append(supplier)

        return suppliers

    def get_data_of_supplier(self, supplier_id, custom_fields=None, exclude_categories=None):
        supplier_url = f"{self._url}suppliers/{str(supplier_id)}/edit"
        parsed_html_body = bs(self._get(supplier_url, self._default_header).content, 'html.parser').body
        category = parsed_html_body.find(id="supplier_supplier_category_id").select_one('option:checked').text # rewrite so it doesn't crash if no category selected
        if category in exclude_categories:
            return None
        name = parsed_html_body.find(id="supplier_name").get("value")
        address = parsed_html_body.find(id="supplier_address").get("value")
        custom_fields = []
        for cf in custom_fields:
            custom_fields.append(parsed_html_body.find(id=f"supplier_custom_fields_{cf.name}")) # doesn't work yet in Foodsoft, it seems

        return Supplier(name=name, address=address, category=category, custom_fields=custom_fields)
