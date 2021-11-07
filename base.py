import csv
import os
import logging
import json
import datetime
import re
import dill
from foodsoft import FSConnector

class Run:
    def __init__(self, foodcoop, configuration, name="", next_possible_methods=[]):
        self.path, self.name = prepare_output(foodcoop=foodcoop, configuration=configuration, name=name)
        self.foodcoop = foodcoop
        self.configuration = configuration
        self.next_possible_methods = next_possible_methods
        self.completion_percentage = 0

    def save(self):
        file_path = os.path.join(self.path, "run.obj")
        with open(file_path, 'wb') as file:
            dill.dump(self, file)

    @classmethod
    def load(cls, path):
        with open(os.path.join(path, "run.obj"), 'rb') as file:
            return dill.load(file)

class ScriptMethod:
    def __init__(self, name, inputs=[]):
        self.name = name
        self.inputs = inputs

class Variable:
    def __init__(self, name, required=False, example=None, description=""):
        self.name = name
        self.required = required
        self.example = example
        self.description = description

class Input:
    def __init__(self, name, required=False, accepted_file_types=[], example=None, description=""):
        self.name = name
        self.required = required
        self.accepted_file_types = accepted_file_types # for example ["csv"], or [] if not a file
        self.example = example # important (if not a file) to know which type of input should be asked for
        self.description = description

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
        self.ignore = ignore # if True, the article will not be imported
        self.orig_unit = orig_unit # Short form of article's unit, used for distinguishing duplicates, not loaded into Foodsoft
        self.temp = temp # for temporary data of the script, not loaded into foodsoft

class Category:
    def __init__(self, number, name="", subcategories=[]):
        self.number = number
        self.name = name
        self.subcategories = subcategories

def remove_double_strings_loop(text, string, description=None, number_of_runs=100):
    loop_count = 0
    while string+string in text:
        text = text.replace(string+string, string)
        loop_count += 1
        if loop_count > number_of_runs:
            if not description:
                description = "'" + string + "'"
            print("\nLoop to replace double " + description + " ran " + number_of_runs + " times for following text:")
            print(text)
            break
    return text

def read_config(foodcoop, configuration="", ensure_subconfig=""):
    filename = "config_" + foodcoop + ".json"
    with open(filename) as json_file:
        config = json.load(json_file)
    if configuration:
        if configuration not in config:
            configuration_config = {}
        else:
            configuration_config = config[configuration]
        if ensure_subconfig:
            if ensure_subconfig not in configuration_config:
                configuration_config[ensure_subconfig] = {}
        return configuration_config
    else:
        return config

def read_in_config(config, detail, alternative=None):
    if detail in config:
        return config[detail]
    else:
        return alternative

def save_config(foodcoop, config):
    filename = "config_" + foodcoop + ".json"
    with open(filename, "w") as json_file:
        json.dump(config, json_file, indent=4)

def save_configuration(foodcoop, configuration, configuration_config):
    config = read_config(foodcoop)
    if configuration not in config:
        config[configuration] = {}
    config[configuration] = configuration_config
    save_config(foodcoop, config)

def rename_configuration(foodcoop, old_configuration_name, new_configuration_name):
    config = read_config(foodcoop)
    if old_configuration_name in config:
        config[new_configuration_name] = config.pop(old_configuration_name)
        save_config(foodcoop, config)
        existing_output_path = output_path(foodcoop, old_configuration_name)
        new_output_path = output_path(foodcoop, new_configuration_name)
        if os.path.exists(new_output_path):
            for entry in os.scandir(existing_output_path):
                new_entry_name = entry.name
                while os.path.exists(os.path.join(new_output_path, new_entry_name)):
                    new_entry_name += "*"
                os.rename(os.path.join(existing_output_path, entry.name), os.path.join(new_output_path, new_entry_name))
            os.rmdir(existing_output_path)
        else:
            os.rename(existing_output_path, new_output_path)
        return new_configuration_name
    else:
        return None

def delete_configuration(foodcoop, configuration):
    config = read_config(foodcoop)
    deleted_configuration = config.pop(configuration, None)
    save_config(foodcoop, config)
    updated_config = read_config(foodcoop)
    if deleted_configuration:
        if deleted_configuration in updated_config.items():
            deleted_configuration = None
    return deleted_configuration

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

def output_path(foodcoop, configuration):
    return os.path.join("output", foodcoop, configuration)

def get_outputs(foodcoop, configuration):
    path = output_path(foodcoop, configuration)
    if os.path.exists(path):
        return [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
    else:
        return []

def get_CSVs(foodcoop, configuration):
    outputs = get_outputs(foodcoop, configuration)
    path = output_path(foodcoop, configuration)
    csv_files = []
    for output in outputs:
        csv_path = os.path.join(path, output, "download")
        if os.path.exists(csv_path):
            CSVs = [os.path.join(csv_path, f) for f in os.listdir(csv_path) if f.endswith(".csv")]
            if len(CSVs) > 1:
                print("Warning: Multiple CSVs found for " + output)
            if CSVs:
                csv_files.append(CSVs[0])
    return csv_files

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
    # get list of articles of the same name, or differing only in upper-/lowercase or whitespaces
    return [a for a in articles if a.name.casefold().replace(" ", "") == article.name.casefold().replace(" ", "")]

def rename_duplicates(articles):
    # Foodsoft requires articles to have a unique name. It is also useful if they can clearly by distinguished e.g. on printed order lists.

    # Check if articles of the same name can be distinguished by their unit, and rename them if so
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

    # For articles of the same name and unit, check if they can be distinguished by their manufacturer, and rename them if so
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
    
    # For articles of the same name and unit which can't be distinguished by their manufacturer, check if they can be distinguished by their origin, and rename them if so
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
    
    # For articles which still couldn't be distinguished, add numbers (1), (2), etc.
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
    if len(articles_from_csv) > 1:
        for row in articles_from_csv[1:]:
            article = Article(order_number=row[1], name=row[2], note=row[3], manufacturer=row[4], origin=row[5], unit=row[6], price_net=row[7], vat=row[8], deposit=row[9], unit_quantity=row[10], category=row[13])
            articles.append(article)
    return articles

def compare_string(article, article_from_last_run, article_from_foodsoft, string_type, configuration_config, notifications):
    if string_type not in ["name", "note", "manufacturer", "origin", "unit", "price_net", "vat", "deposit", "unit_quantity"]:
        notifications.append("Invalid string type for article attribute (look in config file?): " + string_type)
    else:
        replace = False
        if article_from_foodsoft and article_from_last_run:
            if getattr(article, string_type) != getattr(article_from_foodsoft, string_type) and getattr(article, string_type) == getattr(article_from_last_run, string_type):
                replace = True
                replaced_string = getattr(article, string_type)
                manual_string = getattr(article_from_foodsoft, string_type)
                if article.order_number not in configuration_config["manual changes"]:
                    configuration_config["manual changes"][article.order_number] = {}
                configuration_config["manual changes"][article.order_number][string_type] = {}
                configuration_config["manual changes"][article.order_number][string_type]["replaced"] = replaced_string
                configuration_config["manual changes"][article.order_number][string_type]["manual"] = manual_string
                notifications.append("Keeping manual change of article " + string_type + ": " + replaced_string + " -> " + manual_string)
        if not replace and article.order_number in configuration_config["manual changes"]:
            manual_changes = configuration_config["manual changes"][article.order_number]
            if string_type in manual_changes:
                if manual_changes[string_type]["replaced"] == getattr(article, string_type):
                    replace = True
                    manual_string = manual_changes[string_type]["manual"]
        if replace:
            setattr(article, string_type, manual_string)
    return article, configuration_config

def compare_manual_changes(foodcoop, supplier, supplier_id, articles, notifications=[], compare_name=True, compare_note=True, compare_manufacturer=True, compare_origin=True, compare_unit=True, compare_price=True, compare_vat=False, compare_deposit=False, compare_unit_quantity=False, compare_category=True):
    # This is an optional method which checks if article data has been modified manually in Foodsoft after the last CSV was created.
    # In case the article data in the source did not change since the last run of the script and the article data from your Foodsoft instance differs, latter is adopted.

    # Extract the configuration for this supplier
    configuration_config = read_config(foodcoop=foodcoop, configuration=supplier, ensure_subconfig="manual changes")
    foodcoop, foodsoft_url, foodsoft_user, foodsoft_password = read_foodsoft_config()

    # Connect to your Foodsoft instance and download the articles CSV of the supplier
    if foodsoft_url and foodsoft_user and foodsoft_password and supplier_id:
        fsc = FSConnector(url=foodsoft_url, supplier_id=supplier_id, user=foodsoft_user, password=foodsoft_password)
        csv_from_foodsoft = csv.reader(fsc.get_articles_CSV().splitlines(), delimiter=';')
        articles_from_foodsoft = read_articles_from_csv(csv_from_foodsoft)
    else:
        articles_from_foodsoft = []

    # Find the last CSV created by the script
    files = get_CSVs(foodcoop=foodcoop, configuration=supplier)
    if not files:
        notifications.append("No previous CSV found for comparison.")
        articles_from_last_run = []
    else:
        last_csv = files[-1] # TODO: It should be saved in a Config file which CSV was last imported, and then be chosen here
        notifications.append("It was assumed '" + last_csv + "' was the last CSV imported into Foodsoft.")
        with open(last_csv, newline='', encoding='utf-8') as csvfile:
            last_csv_opened = csv.reader(csvfile, delimiter=';')
            articles_from_last_run = read_articles_from_csv(last_csv_opened)

    # Compare for each article the newly readout data, the data from Foodsoft, and the data from the last run
    for article in articles:
        article_from_foodsoft_list = [a for a in articles_from_foodsoft if a.order_number == article.order_number]
        if article_from_foodsoft_list:
            article_from_foodsoft = article_from_foodsoft_list[0]
        else:
            article_from_foodsoft = None
        article_from_last_run_list = [a for a in articles_from_last_run if a.order_number == article.order_number]
        if article_from_last_run_list:
            article_from_last_run = article_from_last_run_list[0]
        else:
            article_from_last_run = None

        if compare_name:
            article, configuration_config = compare_string(article, article_from_last_run, article_from_foodsoft, "name", configuration_config, notifications)
        if compare_note:
            article, configuration_config = compare_string(article, article_from_last_run, article_from_foodsoft, "note", configuration_config, notifications)
        if compare_manufacturer:
            article, configuration_config = compare_string(article, article_from_last_run, article_from_foodsoft, "manufacturer", configuration_config, notifications)
        if compare_origin:
            article, configuration_config = compare_string(article, article_from_last_run, article_from_foodsoft, "origin", configuration_config, notifications)
        if compare_unit:
            article, configuration_config = compare_string(article, article_from_last_run, article_from_foodsoft, "unit", configuration_config, notifications)
        if compare_price:
            article, configuration_config = compare_string(article, article_from_last_run, article_from_foodsoft, "price_net", configuration_config, notifications)
        if compare_vat:
            article, configuration_config = compare_string(article, article_from_last_run, article_from_foodsoft, "vat", configuration_config, notifications)
        if compare_deposit:
            article, configuration_config = compare_string(article, article_from_last_run, article_from_foodsoft, "deposit", configuration_config, notifications)
        if compare_unit_quantity:
            article, configuration_config = compare_string(article, article_from_last_run, article_from_foodsoft, "unit_quantity", configuration_config, notifications)
        if compare_category:
            manual_category = False
            if article.order_number in configuration_config["manual changes"]:
                if "category" in configuration_config["manual changes"][article.order_number]:
                    article.category = configuration_config["manual changes"][article.order_number]["category"]
                    manual_category = True
            if not manual_category and article_from_foodsoft:
                if not article.order_number in configuration_config["manual changes"]:
                    configuration_config["manual changes"][article.order_number] = {}
                configuration_config["manual changes"][article.order_number]["category"] = article_from_foodsoft.category
                article.category = article_from_foodsoft.category

    save_configuration(foodcoop=foodcoop, configuration=supplier, configuration_config=configuration_config)

    return articles, notifications

def validate_string(string, string_type, article, notifications):
    # Check if unit, name, and other strings exceed the respective character limit, and shorten them if so

    string = str(string)
    if string_type != "unit" and string_type != "name": # Units and names could also be shortened, but Foodsoft will validate them, so it's not necessary.
        max_length = 255
        abort_string = "..."
        if len(string) > max_length:
            short_length = max_length - len(abort_string)
            shortened_string = string[0:short_length] + abort_string
            message = "Overlong article " + string_type + " (" + str(len(string)) + " characters) of article #" + str(article.order_number) + " (" + str(article.name) + ") registered, shortened to " + str(len(shortened_string)) + " characters."
            notifications.append(message)
            string = shortened_string

    string.replace(';', ',')
    return string, notifications

def get_data_from_articles(articles, notifications):
    # Transform instances of 'article' class into a table which can be written as a CSV
    rows = []
    for article in articles:

        avail = ''
        if not article.available:
            avail = 'x'

        order_number, notifications = validate_string(article.order_number, 'order number', article, notifications)
        name, notifications = validate_string(article.name, 'name', article, notifications)
        note, notifications = validate_string(article.note, 'note', article, notifications)
        manufacturer, notifications = validate_string(article.manufacturer, 'manufacturer', article, notifications)
        origin, notifications = validate_string(article.origin, 'origin', article, notifications)
        unit, notifications = validate_string(article.unit, 'unit', article, notifications)

        article_data = [avail, order_number, name, note, manufacturer, origin, unit, article.price_net, article.vat, article.deposit, article.unit_quantity, '', '', article.category]
        rows.append(article_data)

    return rows, notifications

def list_categories(categories):
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

def compose_articles_csv_message(supplier, supplier_id=None, categories=[], ignored_categories=[], ignored_subcategories=[], ignored_articles=[], notifications=[], prefix=""):
    foodcoop, foodsoft_url, foodsoft_user, foodsoft_password = read_foodsoft_config()
    text = ""
    if prefix:
        text += prefix + "\n\n"
    text += "Die CSV mit automatisch ausgelesenen Artikeln von " + supplier + " wurde erstellt.\n"
    if foodsoft_url and supplier_id:
        text += "Sie kann unter folgendem Link hochgeladen werden: (Häkchen bei 'Artikel löschen, die nicht in der hochgeladenen Datei sind' setzen!)\n"
        text += foodsoft_url + "suppliers/" + str(supplier_id) + "/articles/upload\n"
    else:
        text += "Sie kann in der Foodsoft hochgeladen werden unter Lieferant -> Artikel -> Artikel hochladen (Häkchen bei 'Artikel löschen, die nicht in der hochgeladenen Datei sind' setzen!)\n"
    if categories:
        text += "\nAusgelesene Kategorien:\n"
        text += list_categories(categories)
    if ignored_categories:
        text += "\nIgnorierte Kategorien:\n"
        text += list_categories(ignored_categories)
    if ignored_subcategories:
        text += "\nIgnorierte Unterkategorien:\n"
        text += list_categories(ignored_subcategories)
    if ignored_articles:
        text += "\nIgnorierte einzelne Artikel:"
        for article in ignored_articles:
            text += "\n#" + str(article.order_number) + " " + article.name + " " + article.unit
            if article.manufacturer:
                text += " von " + article.manufacturer
            if article.origin:
                text += " aus " + article.origin
        text += "\n"
    if notifications:
        text += "\nHinweise:"
        for notification in notifications:
            text += "\n- " + notification
    return text

def prepare_output(foodcoop, configuration, name=""):
    path = "output"
    os.makedirs(path, exist_ok=True)
    path = os.path.join(path, foodcoop)
    os.makedirs(path, exist_ok=True)
    path = os.path.join(path, configuration)
    os.makedirs(path, exist_ok=True)
    if name:
        path = os.path.join(path, name)
        os.makedirs(path, exist_ok=True)
    else:
        name = datetime.date.today().isoformat()
        path = os.path.join(path, name)
        number = 1
        while os.path.isdir(path + "_" + str(number)):
            number += 1
        path += "_" + str(number)
        name += "_" + str(number)
        os.makedirs(path, exist_ok=True)

    return path, name

def file_path(path, folder, file_name):
    path = os.path.join(path, folder)
    os.makedirs(path, exist_ok=True)
    return os.path.join(path, file_name)

def write_articles_csv(file_path, articles, notifications=[]):
    rows, notifications = get_data_from_articles(articles=articles, notifications=notifications)

    with open(file_path + '.csv', 'w', encoding='UTF8', newline='') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(['avail.', 'Order number', 'Name', 'Note', 'Manufacturer', 'Origin', 'Unit', 'Price (net)', 'VAT', 'Deposit', 'Unit quantity', '', '', 'Category'])
        writer.writerows(rows)

    return notifications

def write_txt(file_path, content):
    with open(file_path + ".txt", "w", encoding="UTF8") as f:
        f.write(content)