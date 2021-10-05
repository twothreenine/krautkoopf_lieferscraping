import csv
import os
import datetime
from foodsoft import FSConnector

config = {'foodsoft_url': os.environ['TR_FOODSOFT_URL'],'foodsoft_user': os.environ['TR_FOODSOFT_USER'],'foodsoft_password': os.environ['TR_FOODSOFT_PASS']}

class Article:
    def __init__(self, order_number, name, unit, price_net, available=True, note="", manufacturer="", origin="", vat=0, deposit=0, unit_quantity=1, category="", ignore=False, orig_unit="", temp=""):
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
        self.ignore = ignore
        self.orig_unit = orig_unit # Short form of article's unit, used for distinguishing duplicates, not loaded into Foodsoft
        self.temp = temp # for temporary data of the script, not loaded into foodsoft

class Category:
    def __init__(self, number, name="", subcategories=[]):
        self.number = number
        self.name = name
        self.subcategories = subcategories

def remove_articles_to_ignore(articles):
    return [x for x in articles if not x.ignore]

def suffix(suffix, suffix_type=""):
    word = ""
    if suffix_type:
        if suffix_type == "manufacturer":
            word = "von "
        elif suffix_type == "origin":
            word = "aus "
    return " (" + word + str(suffix) + ")"

def get_duplicates(article, articles):
    return [a for a in articles if a.name.casefold().replace(" ", "") == article.name.casefold().replace(" ", "")]

def rename_duplicates(articles):
    articles_to_rename = {}

    for article in articles:
        articles_of_this_name = get_duplicates(article, articles)
        if len(articles_of_this_name) > 1:
            if article.orig_unit:
                articles_of_this_unit = [a for a in articles_of_this_name if a.orig_unit.casefold().replace(" ", "") == article.orig_unit.casefold().replace(" ", "")]
                if len(articles_of_this_unit) != len(articles_of_this_name):
                    articles_to_rename[article] = article.name + suffix(article.orig_unit)

    for article in articles_to_rename:
        article.name = articles_to_rename[article]

    articles_to_rename = {}

    for article in articles:
        articles_of_this_name = get_duplicates(article, articles)
        if len(articles_of_this_name) > 1:
            if article.manufacturer:
                articles_of_this_manufacturer = [a for a in articles_of_this_name if a.manufacturer.casefold().replace(" ", "") == article.manufacturer.casefold().replace(" ", "")]
                if len(articles_of_this_manufacturer) != len(articles_of_this_name):
                    articles_to_rename[article] = article.name + suffix(article.manufacturer, "manufacturer")

    for article in articles_to_rename:
        article.name = articles_to_rename[article]
        
    articles_to_rename = {}

    for article in articles:
        articles_of_this_name = get_duplicates(article, articles)
        if len(articles_of_this_name) > 1:
            if article.origin:
                articles_of_this_origin = [a for a in articles_of_this_name if a.origin.casefold().replace(" ", "") == article.origin.casefold().replace(" ", "")]
                if len(articles_of_this_origin) != len(articles_of_this_name):
                    articles_to_rename[article] = article.name + suffix(article.origin, "origin")

    for article in articles_to_rename:
        article.name = articles_to_rename[article]
        
    articles_to_rename = {}

    for article in articles:
        articles_of_this_name = get_duplicates(article, articles)
        if len(articles_of_this_name) > 1:
            articles_to_rename[article] = article.name + suffix(articles_of_this_name.index(article) + 1)

    for article in articles_to_rename:
        article.name = articles_to_rename[article]

    return articles

def read_articles_from_csv(csv):
    articles = []
    articles_from_csv = list(csv)
    for row in articles_from_csv[1:]:
        article = Article(order_number=row[1], name=row[2], note=row[3], manufacturer=row[4], origin=row[5], unit=row[6], price_net=row[7], vat=row[8], deposit=row[9], unit_quantity=row[10])
        articles.append(article)
    return articles

def manual_change_message(manual_string, replaced_string, string_type):
    print("\nKeeping manual change of article " + string_type + ": " + replaced_string + " -> " + manual_string)

def compare_manual_changes(articles, supplier, supplier_id, compare_name=True, compare_note=True, compare_manufacturer=True, compare_origin=True, compare_unit=True, compare_price=False, compare_vat=False, compare_deposit=False, compare_unit_quantity=False):
    fsc = FSConnector(url=config['foodsoft_url'], supplier_id=supplier_id, user=config['foodsoft_user'], password=config['foodsoft_password'])
    csv_from_foodsoft = csv.reader(fsc.getCSV().splitlines(), delimiter=';')
    articles_from_foodsoft = read_articles_from_csv(csv_from_foodsoft)

    files = [f for f in os.listdir("output/" + supplier) if os.path.isfile(os.path.join("output/" + supplier, f))]
    last_csv = files[-1]
    with open("output/" + supplier + "/" + last_csv, newline='', encoding='utf-8') as csvfile:
        last_csv_opened = csv.reader(csvfile, delimiter=';')
        articles_from_last_run = read_articles_from_csv(last_csv_opened)

    for article in articles:
        article_from_foodsoft_list = [a for a in articles_from_foodsoft if a.order_number == article.order_number]
        if not article_from_foodsoft_list:
            continue
        article_from_foodsoft = article_from_foodsoft_list[0]
        article_from_last_run_list = [a for a in articles_from_last_run if a.order_number == article.order_number]
        if not article_from_last_run_list:
            continue
        article_from_last_run = article_from_last_run_list[0]

        if compare_name and article.name != article_from_foodsoft.name and article.name == article_from_last_run.name:
            manual_change_message(manual_string=article_from_foodsoft.name, replaced_string=article.name, string_type="name")
            article.name = article_from_foodsoft.name

        if compare_note and article.note != article_from_foodsoft.note and article.note == article_from_last_run.note:
            manual_change_message(manual_string=article_from_foodsoft.note, replaced_string=article.note, string_type="note")
            article.note = article_from_foodsoft.note

        if compare_manufacturer and article.manufacturer != article_from_foodsoft.manufacturer and article.manufacturer == article_from_last_run.manufacturer:
            manual_change_message(manual_string=article_from_foodsoft.manufacturer, replaced_string=article.manufacturer, string_type="manufacturer")
            article.manufacturer = article_from_foodsoft.manufacturer

        if compare_origin and article.origin != article_from_foodsoft.origin and article.origin == article_from_last_run.origin:
            manual_change_message(manual_string=article_from_foodsoft.origin, replaced_string=article.origin, string_type="origin")
            article.origin = article_from_foodsoft.origin

        if compare_unit and article.unit != article_from_foodsoft.unit and article.unit == article_from_last_run.unit:
            manual_change_message(manual_string=article_from_foodsoft.unit, replaced_string=article.unit, string_type="unit")
            article.unit = article_from_foodsoft.unit

        if compare_price and article.price_net != article_from_foodsoft.price_net and article.price_net == article_from_last_run.price_net:
            manual_change_message(manual_string=article_from_foodsoft.price_net, replaced_string=article.price_net, string_type="price_net")
            article.price_net = article_from_foodsoft.price_net

        if compare_vat and article.vat != article_from_foodsoft.vat and article.vat == article_from_last_run.vat:
            manual_change_message(manual_string=article_from_foodsoft.vat, replaced_string=article.vat, string_type="vat")
            article.vat = article_from_foodsoft.vat

        if compare_deposit and article.deposit != article_from_foodsoft.deposit and article.deposit == article_from_last_run.deposit:
            manual_change_message(manual_string=article_from_foodsoft.deposit, replaced_string=article.deposit, string_type="deposit")
            article.deposit = article_from_foodsoft.deposit

        if compare_unit_quantity and article.unit_quantity != article_from_foodsoft.unit_quantity and article.unit_quantity == article_from_last_run.unit_quantity:
            manual_change_message(manual_string=article_from_foodsoft.unit_quantity, replaced_string=article.unit_quantity, string_type="unit_quantity")
            article.unit_quantity = article_from_foodsoft.unit_quantity

    return articles

def validate_string(string, string_type, article):
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
        message = "\nOverlong article " + string_type + " (" + str(len(string)) + " characters) of article #" + str(article.order_number) + " (" + str(article.name) + ") registered, shortened to " + str(len(shortened_string)) + " characters."
        if string_type == "unit" or string_type == "name":
            message += "\nOriginal: " + string + "\nShortened to: " + shortened_string
        print(message)
        string = shortened_string

    string.replace(';', ',')
    return string

def get_data_from_articles(articles):
    rows = []
    for article in articles:

        avail = ''
        if not article.available:
            avail = 'x'

        article_data = [avail, validate_string(article.order_number, 'order number', article), validate_string(article.name, 'name', article), validate_string(article.note, 'note', article), validate_string(article.manufacturer, 'manufacturer', article), 
            validate_string(article.origin, 'origin', article), validate_string(article.unit, 'unit', article), article.price_net, article.vat, article.deposit, article.unit_quantity, '', '', article.category]
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

def compose_message(supplier, categories, ignored_categories, ignored_subcategories, ignored_articles):
    text = "Anbei die Liste an automatisch ausgelesenen Artikeln von " + supplier + ".\n"
    text += "Sie kann unter folgendem Link hochgeladen werden: (Häkchen bei 'Artikel löschen, die nicht in der hochgeladenen Datei sind' setzen!)\n"
    text += "\n" # Link
    text += "\n\nAusgelesene Kategorien:\n"
    text += listCategories(categories)
    if ignored_categories:
        text += "\nIgnorierte Kategorien:\n"
        text += listCategories(ignored_categories)
    if ignored_subcategories:
        text += "\nIgnorierte Unterkategorien:\n"
        text += listCategories(ignored_subcategories)
    if ignored_articles:
        text += "\nIgnorierte Artikel:\n"
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
    if not os.path.exists("output/" + supplier):
        os.makedirs("output/" + supplier)
    file_name = supplier + datetime.date.today().isoformat()
    number = 1
    while os.path.isfile('output/' + supplier + '/' + file_name + '_' + str(number) + '.csv'):
        number += 1

    with open('output/' + supplier + '/' + file_name + '_' + str(number) + '.csv', 'w', encoding='UTF8', newline='') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(['avail.', 'Order number', 'Name', 'Note', 'Manufacturer', 'Origin', 'Unit', 'Price (net)', 'VAT', 'Deposit', 'Unit quantity', '', '', 'Category'])
        writer.writerows(rows)