import requests
from bs4 import BeautifulSoup
import re

r = requests.get('https://www.cafe-libertad.de/kaffee-und-espresso')
soup = BeautifulSoup(r.text, 'html.parser')
products = soup.find_all('div', class_='box-produktliste')
articles = {}
ORIGINS = ['Mexiko', 'Kolumbien', 'Honduras', 'Costa Rica', 'Indien']
for product in products:
    product_name = product.find_all('a').text
    product_name = product_name.replace('Bio-', '')
    product_price = product.find_all('div', class_='preis')
    product_details['price'] = re.search('/d+,/d+', product_price).group()
    product_weight = product.find_all('div', class_='standard text-right').text
    product_weight = product_weight.replace('Inhalt: ', '').replace(' ', '')
    product_notes = product.find_all('div', class_='beschreibung').p.text.split('<br>')
    origin_guess = product_notes[-1].replace('• ', '').replace('Herkunft: ', '')
    intersection = set(ORIGIN).intersects(set(origin_guess.split(' ')))
    if len(intersection) > 0:
        product_details['origin'] = origin_guess
    else:
        get_origin_from_product_page()

    

    articles[] = {}

    def get_origin_from_product_page():
        print(get_origin_from_product_page)
