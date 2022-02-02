#This should work as an object API to connect with foodsoft and
#work with it.

import logging
import requests
import os
import re
from bs4 import BeautifulSoup as bs
import urllib.request

logging.basicConfig(level=logging.DEBUG)

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