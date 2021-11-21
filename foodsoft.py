#This should work as an object API to connect with foodsoft and
#work with it.

from json import dumps
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
    def __init__(self, url, supplier_id, user=None, password=None):
        self._session = None
        self._url = url # logging purpose only?
        self._url_login_request = url + 'login'
        self._url_login_post = url + 'sessions'
        self._url_article_csv = url + 'suppliers/' + str(supplier_id) + "/articles.csv"

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

        if user and password:
            self.login(user, password)

    def _get(self, url, header, data=None):
        if data is None:
            response = self._session.get(url, headers=header)
        if response.status_code != 200:
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
        logging.debug(user + ' logged in sucessfully to ' + self._url)

    def logout(self):
        self._session.close()
        
    def get_articles_CSV(self):
        response = self._get(self._url_article_csv, self._default_header)
        decoded_content = response.content.decode('utf-8')
        return decoded_content