import csv
import os
import datetime

class Article:
    def __init__(self, order_number, name, unit, price_net, available=True, note="", manufacturer="", origin="", vat=0, deposit=0, unit_quantity=1, category="", orig_name="", orig_unit="", temp=""):
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
        self.orig_name = orig_name # for finding duplicates, not loaded into foodsoft
        self.orig_unit = orig_unit # for distinguishing duplicates, not loaded into foodsoft
        self.temp = temp # for temporary data of the script, not loaded into foodsoft

class Category:
    def __init__(self, number, name="", subcategories=[]):
        self.number = number
        self.name = name
        self.subcategories = subcategories

def suffix(suffix):
    return " (" + str(suffix) + ")"

def rename_duplicates(articles):
    for article in articles:
        articles_of_this_name = [a for a in articles if a.orig_name == article.orig_name]
        if len(articles_of_this_name) > 1:
            if article.orig_unit:
                articles_of_this_unit = [a for a in articles_of_this_name if a.orig_unit == article.orig_unit]
                if len(articles_of_this_unit) != len(articles_of_this_name):
                    article.name += suffix(article.orig_unit)

    for article in articles:
        articles_of_this_name = [a for a in articles if a.name == article.name]
        if len(articles_of_this_name) > 1:
            article.name += suffix(articles_of_this_name.index(article) + 1)

    return articles

def validate_string(string, string_type):
    string = str(string)
    if string_type == "unit":
        max_length = 15
        abort_string = "/"
    elif string_type == "name":
        max_length = 60
        abort_string = "/"
    else:
        max_length = 255
        abort_string = "..."
    if len(string) > max_length:
        short_length = max_length - len(abort_string)
        shortened_string = string[0:short_length] + abort_string
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

def listCategories(categories):
    txt = ""
    for category in categories:
        txt += "#" + str(category.number) + " " + category.name
        if category.subcategories:
            subcats = category.subcategories.copy()
            txt += " (inkl. Unterkategorien " + subcats[0].name
            subcats.pop(0)
            for sc in subcats:
                txt += ", " + sc.name
            txt += ")"
        txt += "\n"
    return txt

def send_message(supplier, categories, ignored_categories, ignored_subcategories, ignored_articles):
    text = "Hallo,\n\ndie Liste an automatisch ausgelesenen Artikeln von " + supplier + " befindet sich im Anhang.\n"
    text += "Sie kann unter folgendem Link hochgeladen werden: (Häkchen bei 'Artikel löschen, die nicht in der hochgeladenen Datei sind' setzen!)\n"
    text += "\n" # Link
    text += "\n\nAusgelesene Kategorien:\n"
    text += listCategories(categories)
    if ignored_categories:
        text += "\n\nIgnorierte Kategorien:\n"
        text += listCategories(ignored_categories)
    if ignored_subcategories:
        text += "\n\nIgnorierte Unterkategorien:\n"
        text += listCategories(ignored_subcategories)
    if ignored_articles:
        text += "\n\nIgnorierte Artikel:\n"
        for article in ignored_articles:
            text += "#" + str(article.order_number) + " " + article.name + " " + article.unit
            if article.manufacturer:
                text += " von " + article.manufacturer
            if article.origin:
                text += " aus " + article.origin
    print(text)

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