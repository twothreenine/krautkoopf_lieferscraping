import csv
import copy

import base
import script_libs.generic.foodsoft_article as foodsoft_article

def remove_articles_to_ignore(articles):
    return [x for x in articles if not x.ignore]

def get_duplicates(article, articles, attribute="name", casefold=True, strip=True, remove_whitespaces=False):
    # get list of articles of the same name (or different attribute, if specified), or differing only in upper-/lowercase or whitespaces
    duplicates = []
    compared_attribute_of_article = getattr(article, attribute)
    if casefold:
        compared_attribute_of_article = str(compared_attribute_of_article).casefold()
    if remove_whitespaces:
        compared_attribute_of_article = str(compared_attribute_of_article).replace(" ", "")
    elif strip:
        compared_attribute_of_article = str(compared_attribute_of_article).strip()

    for a in articles:
        compared_attribute = getattr(a, attribute)
        if casefold:
            compared_attribute = str(compared_attribute).casefold()
        if remove_whitespaces:
            compared_attribute = str(compared_attribute).replace(" ", "")
        elif strip:
            compared_attribute = str(compared_attribute).strip()
        if compared_attribute == compared_attribute_of_article:
            duplicates.append(a)
    return duplicates
    # return [a for a in articles if a.name.casefold().replace(" ", "") == article.name.casefold().replace(" ", "")]

def rename_duplicates_by_attribute(articles, notifications, attribute):
    articles_to_rename = {}
    for article in articles:
        articles_of_this_name = get_duplicates(article, articles, remove_whitespaces=True)
        if len(articles_of_this_name) > 1:
            if getattr(article, attribute, False):
                articles_of_this_attribute = [a for a in articles_of_this_name if getattr(a, attribute).casefold().replace(" ", "") == getattr(article, attribute).casefold().replace(" ", "")]
                if len(articles_of_this_attribute) != len(articles_of_this_name):
                    articles_to_rename[article] = article.name + foodsoft_article.suffix(getattr(article, attribute), attribute)
    for article in articles_to_rename:
        article.name = articles_to_rename[article]
    return articles

def rename_duplicates(locales, articles, notifications, compare_orig_unit=True, compare_unit=False, compare_manufacturer=True, compare_origin=True, compare_category=True, keep_full_duplicates=True):
    # Foodsoft requires articles to have a unique name. It is also useful if they can clearly by distinguished e.g. on printed order lists.

    if compare_orig_unit:
        # Check if articles of the same name can be distinguished by their orig unit, and rename them if so
        articles = rename_duplicates_by_attribute(articles, notifications, "orig_unit")

    if compare_unit:
        # Check if articles of the same name can be distinguished by their unit, and rename them if so
        articles = rename_duplicates_by_attribute(articles, notifications, "unit")

    if compare_manufacturer:
        # For articles of the same name and unit, check if they can be distinguished by their manufacturer, and rename them if so
        articles = rename_duplicates_by_attribute(articles, notifications, "manufacturer")
    
    if compare_origin:
        # For articles of the same name, unit, and manufacturer, check if they can be distinguished by their origin, and rename them if so
        articles = rename_duplicates_by_attribute(articles, notifications, "origin")
    
    if compare_category:
        # For articles of the same name, unit, manufacturer, and origin, check if they can be distinguished by their category, and rename them if so
        articles = rename_duplicates_by_attribute(articles, notifications, "category")

    # For articles which still couldn't be distinguished, add numbers (1), (2), etc.
    articles_to_rename = {}
    for article in articles:
        articles_of_this_name = get_duplicates(article, articles, remove_whitespaces=True)
        if len(articles_of_this_name) > 1:
            if keep_full_duplicates:
                articles_to_rename[article] = article.name + foodsoft_article.suffix(articles_of_this_name.index(article) + 1)
            else:
                for article_to_be_removed in articles_of_this_name[1:]:
                    notifications.append(locales["foodsoft_article_import"]["presumed duplicate removed"].format(article_name=article_to_be_removed.name))
                    articles.remove(article_to_be_removed)
    for article in articles_to_rename:
        article.name = articles_to_rename[article]

    return articles, notifications

def rename_duplicate_order_numbers(locales, articles, notifications):
    for article in articles:
        articles_of_this_number = get_duplicates(article, articles, attribute="order_number")
        if len(articles_of_this_number) > 1:
            notifications.append(locales["foodsoft_article_import"]["duplicate order numbers renamed"].format(order_number=article.order_number, times=str(len(articles_of_this_number))))
            for a in articles_of_this_number:
                index_number = articles_of_this_number.index(a)
                new_order_number = f"{str(a.order_number)}_{str(index_number)}"
                while new_order_number in [art for art in articles if art.order_number.casefold().strip() == new_order_number.casefold().strip() and not art == a]:
                    index_number += 1
                    new_order_number = f"{str(a.order_number)}_{str(index_number)}"
                a.order_number = new_order_number
    return articles, notifications

def remove_articles_with_duplicate_order_numbers(locales, articles, notifications):
    for article in articles:
        articles_of_this_number = get_duplicates(article, articles, "order_number")
        if len(articles_of_this_number) > 1:
            # keep the article with the lowest price and most information
            articles_of_this_number.sort(key=lambda x: x.price_net)
            articles_of_this_price = get_duplicates(articles_of_this_number[0], articles_of_this_number, "price_net")
            articles_of_this_price.sort(key=lambda x: (len(x.origin), len(x.manufacturer), len(x.note)), reverse=True)
            articles_to_be_removed = [a for a in articles_of_this_number if a not in articles_of_this_price]
            if len(articles_of_this_price) > 1:
                articles_to_be_removed.extend(articles_of_this_price[1:])
            for article_to_be_removed in articles_to_be_removed:
                notifications.append(locales["foodsoft_article_import"]["presumed duplicate removed"].format(article_name=f"{article_to_be_removed.name} ({article_to_be_removed.price_net})"))
                articles.remove(article_to_be_removed)
    return articles, notifications

def compare_string(locales, article, article_from_last_run, article_from_foodsoft, string_type, configuration_config, notifications, article_order_number=None):
    if string_type not in ["name", "note", "manufacturer", "origin", "unit", "price_net", "vat", "deposit", "unit_quantity"]:
        notifications.append(locales["foodsoft_article_import"].get("invalid string type for article attribute") + string_type)
    else:
        if not article_order_number:
            article_order_number = article.order_number
        replace = False
        if article_from_foodsoft and article_from_last_run:
            if getattr(article, string_type) != getattr(article_from_foodsoft, string_type) and getattr(article, string_type) == getattr(article_from_last_run, string_type):
                replace = True
                replaced_string = getattr(article, string_type)
                manual_string = getattr(article_from_foodsoft, string_type)
                # Problem with article_order_number: If two articles with the same names and units appear in different categories, they will be treated as the same article
                # -> make sure a unique order_number (without category number prefix) is given to each article!
                if article_order_number not in configuration_config["manual changes"]:
                    configuration_config["manual changes"][article_order_number] = {}
                configuration_config["manual changes"][article_order_number][string_type] = {}
                configuration_config["manual changes"][article_order_number][string_type]["replaced"] = replaced_string
                configuration_config["manual changes"][article_order_number][string_type]["manual"] = manual_string
                notifications.append(locales["foodsoft_article_import"]["keeping manual change"].format(article_number=str(article.order_number), article_name=str(article.name), string_type=locales["foodsoft_article"].get(string_type), replaced_string=replaced_string, manual_string=manual_string))
        if not replace and article_order_number in configuration_config["manual changes"]:
            manual_changes = configuration_config["manual changes"][article_order_number]
            if string_type in manual_changes:
                if manual_changes[string_type]["replaced"] == getattr(article, string_type):
                    replace = True
                    manual_string = manual_changes[string_type]["manual"]
        if replace:
            setattr(article, string_type, manual_string)
    return article, configuration_config

def get_articles_from_foodsoft(locales, supplier_id, foodsoft_connector=None, version_delimiter=None, prefix_delimiter=None, skip_unavailable_articles=False, notifications=None):
    # Connect to your Foodsoft instance and download the articles CSV of the supplier

    if not notifications:
        notifications = []

    if foodsoft_connector and supplier_id:
        # fsc = foodsoft.FSConnector(url=foodsoft_url, user=foodsoft_user, password=foodsoft_password)
        csv_from_foodsoft = csv.reader(foodsoft_connector.get_articles_CSV(supplier_id=supplier_id).splitlines(), delimiter=';')
        # fsc.logout()
        articles_from_foodsoft = foodsoft_article.read_articles_from_csv(csv=csv_from_foodsoft, version_delimiter=version_delimiter, prefix_delimiter=prefix_delimiter, skip_unavailable_articles=skip_unavailable_articles)
    else:
        articles_from_foodsoft = []
        warning = locales["foodsoft_article_import"].get("comparing manual changes failed due to missing foodsoft connector")
        notifications.append(warning)
        print(warning)
    return articles_from_foodsoft, notifications

def compare_manual_changes(locales, foodcoop, supplier, articles, articles_from_foodsoft, version_delimiter=None, prefix_delimiter=None, notifications=None, compare_name=True, compare_note=True, compare_manufacturer=True, compare_origin=True, compare_unit=True, compare_price=True, compare_vat=True, compare_deposit=True, compare_unit_quantity=True, compare_category=True, last_imported_csv_containing=""):
    """
    This is an optional method which checks if article data has been modified manually in Foodsoft after the last CSV was created.
    In case the article data in the source did not change since the last run of the script and the article data from your Foodsoft instance differs, latter is adopted.
    """

    if not notifications:
        notifications = []

    # Extract the configuration for this supplier
    configuration_config = base.read_config(foodcoop=foodcoop, configuration=supplier)
    if "manual changes" not in configuration_config:
        configuration_config["manual changes"] = {}

    # Get the last CSV created by the script
    last_imported_run_name = configuration_config.get("last imported run", "")
    last_imported_csv = None
    if last_imported_run_name:
        last_imported_csv, notifications = base.get_file_path(foodcoop=foodcoop, configuration=supplier, run=last_imported_run_name, folder="download", containing=last_imported_csv_containing, ending=".csv", notifications=notifications)
    if not last_imported_csv:
        notifications.append(locales["foodsoft_article_import"].get("no previous CSV found"))
        articles_from_last_run = []
    else:
        notifications.append(locales["foodsoft_article_import"]["assumed last CSV imported"].format(last_imported_csv=last_imported_csv))
        with open(last_imported_csv, newline='', encoding='utf-8') as csvfile:
            last_csv_opened = csv.reader(csvfile, delimiter=';')
            articles_from_last_run = foodsoft_article.read_articles_from_csv(csv=last_csv_opened, version_delimiter=version_delimiter, prefix_delimiter=prefix_delimiter)

    # Compare for each article the newly readout data, the data from Foodsoft, and the data from the last run
    for article in articles:
        article_order_number = article.order_number
        if prefix_delimiter:
            order_number_strings = article_order_number.split(prefix_delimiter)
            if len(order_number_strings) > 1:
                article_order_number = prefix_delimiter.join(order_number_strings[1:])

        article_from_foodsoft_list = [a for a in articles_from_foodsoft if a.order_number == article_order_number]
        if article_from_foodsoft_list:
            article_from_foodsoft = article_from_foodsoft_list[0]
        else:
            article_from_foodsoft = None
        article_from_last_run_list = [a for a in articles_from_last_run if a.order_number == article_order_number]
        if article_from_last_run_list:
            article_from_last_run = article_from_last_run_list[0]
        else:
            article_from_last_run = None

        if compare_name:
            article, configuration_config = compare_string(locales, article, article_from_last_run, article_from_foodsoft, "name", configuration_config, notifications, article_order_number)
        if compare_note:
            article, configuration_config = compare_string(locales, article, article_from_last_run, article_from_foodsoft, "note", configuration_config, notifications, article_order_number)
        if compare_manufacturer:
            article, configuration_config = compare_string(locales, article, article_from_last_run, article_from_foodsoft, "manufacturer", configuration_config, notifications, article_order_number)
        if compare_origin:
            article, configuration_config = compare_string(locales, article, article_from_last_run, article_from_foodsoft, "origin", configuration_config, notifications, article_order_number)
        if compare_unit:
            article, configuration_config = compare_string(locales, article, article_from_last_run, article_from_foodsoft, "unit", configuration_config, notifications, article_order_number)
        if compare_price:
            article, configuration_config = compare_string(locales, article, article_from_last_run, article_from_foodsoft, "price_net", configuration_config, notifications, article_order_number)
        if compare_vat:
            article, configuration_config = compare_string(locales, article, article_from_last_run, article_from_foodsoft, "vat", configuration_config, notifications, article_order_number)
        if compare_deposit:
            article, configuration_config = compare_string(locales, article, article_from_last_run, article_from_foodsoft, "deposit", configuration_config, notifications, article_order_number)
        if compare_unit_quantity:
            article, configuration_config = compare_string(locales, article, article_from_last_run, article_from_foodsoft, "unit_quantity", configuration_config, notifications, article_order_number)
        if compare_category:
            manual_category = False
            if article_order_number in configuration_config["manual changes"]:
                if "category" in configuration_config["manual changes"][article_order_number]:
                    article.category = configuration_config["manual changes"][article_order_number]["category"]
                    manual_category = True
            if not manual_category and article_from_foodsoft:
                if not article_order_number in configuration_config["manual changes"]:
                    configuration_config["manual changes"][article_order_number] = {}
                configuration_config["manual changes"][article_order_number]["category"] = article_from_foodsoft.category
                article.category = article_from_foodsoft.category

    base.save_config(foodcoop=foodcoop, configuration=supplier, config=configuration_config)

    return articles, notifications

def version_articles(articles, articles_from_foodsoft, version_delimiter, compare_name=True, compare_unit=True, compare_unit_quantity=True):
    """
    Check if name, unit, and unit quantity would be altered when importing CSV. If so, mark the article as a new version.
    """
    for article in articles:
        make_new_version = False
        article_from_foodsoft_list = [a for a in articles_from_foodsoft if a.order_number == article.order_number]
        if article_from_foodsoft_list:
            article_from_foodsoft = article_from_foodsoft_list[0]
            if compare_name:
                if article.name != article_from_foodsoft.name:
                    make_new_version = True
            if compare_unit and not make_new_version:
                if article.unit != article_from_foodsoft.unit:
                    make_new_version = True
            if compare_unit_quantity and not make_new_version:
                if article.unit_quantity != article_from_foodsoft.unit_quantity:
                    make_new_version = True
        if make_new_version:
            article.version = article_from_foodsoft.version + 1
    return articles


def recalculate_unit_for_article(article, category_names, recalculate_units, recalculate_unit_quantity=False, add_base_price_to_name=True):
    """
    Transforms a single article into a list of articles with new custom units.
    category_names is expected to be a list (e.g. [original_category, renamed_category]).
    recalculate_units is expected to be a dictionary of the following layout:
    {"Obst & Gemüse": {"categories": ["Obst & Gemüse"], "articles": ["Kartoffeln"], "original units": ["kg", "1kg", "1 kg"], "replacement units": {"500g": 0.5}}, "Äpfel": {"categories": ["Äpfel"], "original units": ["kg", "1kg", "1 kg"], "replacement units": {"500g": 0.5}}}
    Or in yaml style:
    Obst & Gemüse:              # name of recalculate subdict, does not matter later
        categories:             # list of categories for which units will be recalculated
        - Obst & Gemüse
        - Äpfel
        categories case-sensitive: False    # default False
        categories exact: True              # default False (if False: containing strings check)
        original units:         # list of units which will be replaced
        - kg
        - 1kg
        - 1 kg
        replacement units:      # list of new units, consisting of a string (will be shown) and a float number describing the ratio to the original unit (replacement_unit_factor)
            500g: 0.5
        show base price: False  # default True (add price per original unit in article name)
    Käferbohnen:
        articles:               # instead or additionally to categories, this can also be applied to certain articles (applied if article OR category matches)
        - Käferbohnen
        articles case-sensitive: False      # default False
        articles exact: True                # default False (if False: containing strings check)
        intersection: False                 # if both categories and articles are listed, this setting determines if both have to match (intersection) or if either is enough; default is False
        original units:
        - kg
        replacement units:
            1/4 kg: 0.25
            1/2 kg: 0.5
    Eier:
        articles:
        - Eier
        original units:
        - Stk
        replacement units:
            Stk: 1
            6er Pkg: 6
            10er Pkg: 10
    rest:
        any: True               # if this is set, categories and article filters will be ignored and the rule will be applied to all remaining articles (default: False)
        original units:
        - kg
        replacement units:
            500 g: 0.5

    Note that only the first matching recalculating subdict will be applied (break statement).
    """
    articles = []
    for subdict in recalculate_units:
        recalculate_units_units = recalculate_units[subdict].get("original units")
        if recalculate_units_units:
            units_matching = base.equal_strings_check(list1=[article.unit], list2=recalculate_units_units)
        else:
            units_matching = True # if no original units specified, take all

        if units_matching:
            recalculate_for_categories = recalculate_units[subdict].get("categories", [])
            categories_case_sensitive = recalculate_units[subdict].get("categories case-sensitive", False)
            categories_matching = False
            if recalculate_for_categories:
                if recalculate_units[subdict].get("categories exact", False):
                    categories_matching = base.equal_strings_check(list1=category_names, list2=recalculate_for_categories, case_sensitive=categories_case_sensitive)
                else:
                    categories_matching = base.containing_strings_check(list1=category_names, list2=recalculate_for_categories, case_sensitive=categories_case_sensitive)
            recalculate_for_articles = recalculate_units[subdict].get("articles", [])
            articles_matching = False
            if recalculate_for_articles:
                articles_case_sensitive = recalculate_units[subdict].get("articles case-sensitive", False)
                if recalculate_units[subdict].get("articles exact", False):
                    articles_matching = base.equal_strings_check(list1=[article.name], list2=recalculate_for_articles, case_sensitive=categories_case_sensitive)
                else:
                    articles_matching = base.containing_strings_check(list1=[article.name], list2=recalculate_for_articles, case_sensitive=categories_case_sensitive)
            matching = False
            if recalculate_units[subdict].get("any", False):
                matching = True
            elif recalculate_units[subdict].get("intersection", False):
                if categories_matching and articles_matching:
                    matching = True
            elif categories_matching or articles_matching:
                    matching = True

            if matching:
                if add_base_price_to_name:
                    article_name_with_base_price = article.name + f" ({base_price_str(article_price=article.price_net, base_unit=article.unit, vat=article.vat)})"
                else:
                    article_name_with_base_price = article.name
                    article.base_price = article.price_net
                    article.base_unit = article.unit
                for replacement_unit_str, replacement_unit_factor in recalculate_units[subdict].get("replacement units", {}).items():
                    article_in_replacement_unit = copy.deepcopy(article)
                    article_in_replacement_unit = replace_unit(article=article_in_replacement_unit, replacement_unit_str=replacement_unit_str, replacement_unit_factor=replacement_unit_factor, recalculate_unit_quantity=recalculate_unit_quantity)
                    if recalculate_units[subdict].get("show base price", True) and not replacement_unit_factor == 1:
                        article_in_replacement_unit.name = article_name_with_base_price
                    articles.append(article_in_replacement_unit)
                break # TODO: make optional?
    if not articles:
        articles = [article]
    return articles

def create_loose_offer(article, product, create_loose_offers, category_names=None, amount_mode=False):
    """
    Transforms an article with a single unit (unit_quantity = 1) into an article consisting of parcels.
    E.g. a bag of 5 kg into 10 x 0.5 kg, to allow order groups to order smaller amounts.
    category_names is expected to be a list (e.g. [original_category, renamed_category]).
    create_loose_offers is expected to be a dictionary of the following layout ... TODO
    amount_mode: If True, then article.amount is transformed instead of article.unit. article.amount is expected to be a float in the base unit (e.g. 0.5 for 0.5 kg).


    """

    for subdict in create_loose_offers:
        pass # TODO

def resort_articles_in_categories(article_name, category_name, resort_articles_in_categories, return_original=True):
    """
    Delivers an alternative category name based on the config item resort_articles_in_categories.
    resort_articles_in_categories is expected to be a dictionary of the following layout:
    {"Kategorie 1": {"exact": False, "case-sensitive": False, "original categories": ["Obst & Gemüse", "Äpfel"], "target categories": {"Fruchtgemüse": ["Zucchini", "tomate"]}, "rest": "Sonstiges"}}
    Or in yaml style:
    Kategorie 1:
        exact: False            # default False
        case-sensitive: False   # default False
        original categories:    # category_name is checked for matches in these strings
        - Obst & Gemüse
        - Äpfel
        target categories:
            Fruchtgemüse:
            - Zucchini          # if article_name matches this string, "Fruchtgemüse" will be returned as new category name
            - tomate
        rest: Sonstiges         # if neither "Zucchini" nor "tomate" is found in article_name, "Sonstiges" will be returned as new category name

    You can choose if you want to use "target categories" and/or "rest", both are optional.
    If "rest" is not specified and none of the target categories' strings match, the original category_name will be returned, unless return_original is set to False, then None will be returned.
    """
    for resort_category in resort_articles_in_categories:
        exact = resort_articles_in_categories[resort_category].get("exact")
        case_sensitive = resort_articles_in_categories[resort_category].get("case-sensitive")
        if exact:
            if base.equal_strings_check(list1=[category_name], list2=resort_articles_in_categories[resort_category].get("original categories", []), case_sensitive=case_sensitive):
                for target_category, target_category_products in resort_articles_in_categories[resort_category].get("target categories", {}).items():
                    if base.equal_strings_check(list1=[article_name], list2=target_category_products, case_sensitive=case_sensitive):
                        return target_category
                if rest_category := resort_articles_in_categories[resort_category].get("rest"):
                    return rest_category
        else:
            if base.containing_strings_check(list1=[category_name], list2=resort_articles_in_categories[resort_category].get("original categories", []), case_sensitive=case_sensitive):
                for target_category, target_category_products in resort_articles_in_categories[resort_category].get("target categories", {}).items():
                    if base.containing_strings_check(list1=[article_name], list2=target_category_products, case_sensitive=case_sensitive):
                        return target_category
                if rest_category := resort_articles_in_categories[resort_category].get("rest"):
                    return rest_category
    if return_original:
        return category_name

def insert_category_numbers(category_numbering: dict[str, str], new_categories: list[base.Category]) -> dict[str, str]:
    """
    Useful if you want to generate order_numbers for articles starting with a category 'number' – if there's no article number given in the price list.
    category_numbering is expected to be a dictionary of the following layout:
    {{'Vegetables': '00'}, {'Fruits': '01'}, ...}
    If new_categories = ['Vegetables', 'Bread', 'Dry goods', 'Fruits', ...] then 'Bread' will be given the number '00i' and 'Dry goods' '00ii' (i for inserted).
    This preserves the original category numbering, not altering the corresponding article order_numbers (e.g. '01_Strawberries').
    """

    for c in new_categories:
        old_category_number = next((category_numbering[pc] for pc in category_numbering if pc == c.name), None)
        if not old_category_number:
            # skip for now: ask user for matching / match similar strings
            new_categories_before = new_categories[0:new_categories.index(c)]
            if new_categories_before:
                last_of_categories_before = new_categories_before.pop(-1)
                category_numbering[str(c.name)] = category_numbering[last_of_categories_before] + "i" # e.g. 01iii, i for inserted
            elif category_numbering:
                category_numbering[str(c.name)] = category_numbering[next(iter(category_numbering))] + "i"
            else:
                category_numbering[str(c.name)] = "00i"
    
    return category_numbering

def base_price_str(article_price, base_unit, vat=0, with_decimals=True):
    # used in combination with recalculate_unit_for_article
    if article_price:
        gross_price = article_price + article_price * vat / 100
        if with_decimals:
            price_str = '{:.2f}'.format(round(gross_price, 2)).replace('.', ',')
        else:
            price_str = 'ca. ' + str(round(gross_price))
        return f"{price_str} € / {base_unit}"
    else:
        return f"? € / {base_unit}"

def replace_unit(article, replacement_unit_str, replacement_unit_factor, recalculate_unit_quantity):
    # used in combination with recalculate_unit_for_article
    article.unit = replacement_unit_str
    if article.price_net:
        if recalculate_unit_quantity:
            old_article_quantity = article.unit_quantity
            article.unit_quantity = round(article.unit_quantity / replacement_unit_factor)
            replacement_unit_factor = old_article_quantity / article.unit_quantity
        article.price_net = round(article.price_net * replacement_unit_factor, 2)
    return article

def create_articles_from_dict(dict):
    """
    Creates a list of articles from a dictionary/YAML specification, useful for including additional articles 
    (which are not present in the read-out source) by specifying them in the configuration.

    dict is expected to be a dictionary of the following layout:
    {"Vegetables": {"Article 1 Name": {"unit": "1 kg", "price net": 10.9}, "another article": {"order number": 123, "unit": "1 kg", "unit quantity": 10, "price net": 10.9, "vat": 10, "deposit": 0.5, "origin": "1234 Place", "manufacturer": "someone", "note": "large pieces", "available": False}}}

    Or in YAML style:
    Vegetables:                     # specify category name in the superkey (applied to all subitems)
        Article 1 Name:             # specify the article name in the subkey
            unit: 1 kg              # unit and price net are the only mandatory attributes
            price net: 10.9
        another article:
            unit: 1 kg
            price net: 10.9
            order number: 123       # default: article name
            unit quantity: 10       # default: 1
            vat: 10                 # default: 0
            deposit: 0.5            # default: 0
            origin: 1234 Place      # default: ""
            manufacturer: someone   # default: ""
            note: large pieces      # default: ""
            available: False        # default: True
    """
    
    articles = []
    notifications = []
    for category, article_data in dict.items():
        for name, attributes in article_data.items():
            price_net = attributes.get("price net")
            unit = attributes.get("unit")
            if not (price_net and unit):
                notifications.append(f"Failed to create additional article '{name}': 'price net' and/or 'unit' not specified in configuration")
                continue
            articles.append(foodsoft_article.Article(order_number = attributes.get("order number", name), 
                                                    name=name, 
                                                    unit=unit, 
                                                    price_net=price_net, 
                                                    available = attributes.get("available", True), 
                                                    note = attributes.get("note"), 
                                                    manufacturer = attributes.get("manufacturer"), 
                                                    origin = attributes.get("origin"), 
                                                    vat = attributes.get("vat"), 
                                                    deposit = attributes.get("deposit"), 
                                                    unit_quantity = attributes.get("unit quantity"), 
                                                    category = category))
    return articles, notifications

def validate_string(locales, string, string_type, article, notifications):
    """
    Check if unit, name, and other strings exceed the respective character limit, and shorten them if so
    """
    string = base.remove_double_strings_loop(text=str(string), string=" ", description="whitespaces") # remove unnecessary whitespaces
    if string_type != "unit" and string_type != "name": # Units and names could also be shortened, but Foodsoft will validate them, so it's not necessary.
        max_length = 255
        abort_string = "..."
        if len(string) > max_length:
            short_length = max_length - len(abort_string)
            shortened_string = string[0:short_length] + abort_string
            notifications.append(locales["foodsoft_article_import"]["overlong string shortened"].format(string_type=string_type, orig_str_length=str(len(string)), article_number=str(article.order_number), article_name=str(article.name), shortened_string_length=str(len(shortened_string))))
            string = shortened_string

    string.replace(';', ',')
    return string, notifications

def get_data_from_articles(locales, articles, notifications, version_delimiter=None):
    """
    Transform instances of 'article' class into a table which can be written as a CSV
    """
    rows = []
    for article in articles:

        avail = ''
        if not article.available:
            avail = 'x'

        order_number_string = article.order_number
        if version_delimiter and article.version != 1:
            order_number_string = version_delimiter.join([str(article.order_number), str(article.version)])

        order_number, notifications = validate_string(locales, order_number_string, 'order number', article, notifications)
        name, notifications = validate_string(locales, article.name, 'name', article, notifications)
        note, notifications = validate_string(locales, article.note, 'note', article, notifications)
        manufacturer, notifications = validate_string(locales, article.manufacturer, 'manufacturer', article, notifications)
        origin, notifications = validate_string(locales, article.origin, 'origin', article, notifications)
        unit, notifications = validate_string(locales, article.unit, 'unit', article, notifications)

        article_data = [avail, order_number, name, note, manufacturer, origin, unit, article.price_net, article.vat, article.deposit, article.unit_quantity, '', '', article.category]
        rows.append(article_data)

    return rows, notifications

def compose_articles_csv_message(locales, supplier, foodsoft_url=None, supplier_id=None, categories=None, ignored_categories=None, ignored_subcategories=None, ignored_articles=None, notifications=None, prefix=""):
    text = ""
    if prefix:
        text += prefix + "\n\n"
    text += locales["foodsoft_article_import"]["csv created"].format(supplier=supplier) + "\n"
    if foodsoft_url and supplier_id:
        text += f'{locales["foodsoft_article_import"]["csv upload link"]} ({locales["foodsoft_article_import"]["set check to delete articles not in file"]})\n'
        text += foodsoft_url + "suppliers/" + str(supplier_id) + "/articles/upload\n"
    else:
        text += f'{locales["foodsoft_article_import"]["csv upload note without link"]} ({locales["foodsoft_article_import"]["set check to delete articles not in file"]})\n'
    if categories:
        text += f'\n{locales["foodsoft_article_import"]["readout categories"]}:\n'
        text += base.list_categories(locales, categories)
    if ignored_categories:
        text += f'\n{locales["foodsoft_article_import"]["ignored categories"]}:\n'
        text += base.list_categories(locales, ignored_categories)
    if ignored_subcategories:
        text += f'\n{locales["foodsoft_article_import"]["ignored subcategories"]}:\n'
        text += base.list_categories(locales, ignored_subcategories)
    if ignored_articles:
        text += f'\n{locales["foodsoft_article_import"]["ignored single articles"]}:'
        for article in ignored_articles:
            text += "\n#" + str(article.order_number) + " " + article.name + " " + article.unit
            if article.manufacturer:
                text += f' {locales["foodsoft_article"]["by (supplier)"]} {article.manufacturer}'
            if article.origin:
                text += f' {locales["foodsoft_article"]["from (origin)"]} {article.origin}'
        text += "\n"
    if notifications:
        text += f'\n{locales["foodsoft_article_import"]["notifications"]}:'
        for notification in notifications:
            text += "\n- " + notification
    return text

def write_articles_csv(locales, file_path, articles, version_delimiter=None, notifications=None):
    if not notifications:
        notifications = []
    
    rows, notifications = get_data_from_articles(locales=locales, articles=articles, notifications=notifications, version_delimiter=version_delimiter)

    with open(file_path + '.csv', 'w', encoding='UTF8', newline='') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(['avail.', 'Order number', 'Name', 'Note', 'Manufacturer', 'Origin', 'Unit', 'Price (net)', 'VAT', 'Deposit', 'Unit quantity', '', '', 'Category'])
        writer.writerows(rows)

    return notifications
