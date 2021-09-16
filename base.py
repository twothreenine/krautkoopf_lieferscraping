import csv
import os
import datetime

class Article:
    def __init__(self, order_number, name, unit, price_net, available=True, note="", manufacturer="", origin="", vat=0, deposit=0, unit_quantity=1, category=""):
        self.available = available
        self.order_number = order_number
        self.name = name
        self.note = note
        self.manufacturer = manufacturer
        self.origin = origin
        self.unit = unit
        self.price_net = price_net
        self.vat = vat
        self.deposit = deposit
        self.unit_quantity = unit_quantity
        self.category = category

def validate_string(string, string_type):
    string = str(string)
    if len(string) > 255:
        shortened_string = string[0:252] + '...'
        print("Overlong article " + string_type + " (" + str(len(string)) + " characters) registered:")
        print(string)
        print("shortened to:")
        print(shortened_string)
        string = shortened_string

    string.replace(';', ',')
    return string

def get_data_from_articles(articles):
    rows = []
    for article in articles:

        avail = ''
        if not article.available:
            avail = 'x'

        article_data = [avail, validate_string(article.order_number, 'order number'), validate_string(article.name, 'name'), validate_string(article.note, 'note'), validate_string(article.manufacturer, 'manufacturer'), 
            validate_string(article.origin, 'origin'), validate_string(article.unit, 'unit'), article.price_net, article.vat, article.deposit, article.unit_quantity, '', '', article.category]
        rows.append(article_data)

    return rows

def write_csv(supplier, articles):
    rows = get_data_from_articles(articles=articles)

    if not os.path.exists("output"):
        os.makedirs("output")
    file_name = supplier + datetime.date.today().isoformat()
    number = 1
    while os.path.isfile('output/' + file_name + '_' + str(number) + '.csv'):
        number += 1

    with open('output/' + file_name + '_' + str(number) + '.csv', 'w', encoding='UTF8', newline='') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(['avail.', 'Order number', 'Name', 'Note', 'Manufacturer', 'Origin', 'Unit', 'Price (net)', 'VAT', 'Deposit', 'Unit quantity', '', '', 'Category'])
        writer.writerows(rows)