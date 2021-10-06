from bs4 import BeautifulSoup
import requests
import re
import base

# Arguments which should be outsourced into the config file (TODO)
supplier = "Biohof Pranger"
supplier_id = 99 # ID of the supplier in Foodsoft instance
categories_to_ignore = [3, 8]
subcategories_to_ignore = [25, 26, 47]
articles_to_ignore = []

# Global variables
categories = []
articles = []
ignored_categories = []
ignored_subcategories = []
ignored_articles = []
notifications = []

menu = BeautifulSoup(requests.get("https://oekobox-online.eu/v3/shop/pranger/s2/C6.0.222C/categories.jsp?intern=1").text, features="html.parser")

class PriceOption:
    def __init__(self, price, unit):
        self.price = price
        self.unit = unit

def getSubcategories(id):
    subcats = []
    print('sg'+str(id))
    category = base.Category(number=id)
    category.subcategories = []
    subgroup = menu.body.find(id=('sg'+str(id)))
    if subgroup:
        subcat_links = subgroup.find_all('a')
        for sc in subcat_links:
            no = sc['href'].split("id=")[-1]
            name = sc.get_text().strip()
            subcategory = base.Category(number="s"+str(no), name=name)
            if int(no) in subcategories_to_ignore:
                ignored_subcategories.append(subcategory)
                ignore = True
            else:
                category.subcategories.append(subcategory)
                ignore = False
            parsed_html = BeautifulSoup(requests.get("https://oekobox-online.eu/v3/shop/pranger/s2/C6.0.219C/"+sc['href']).text, features="html.parser")
            table = parsed_html.body.find_all('table')
            subcats.append({"name" : name, "number" : "s"+str(no), "items" : table, "ignore" : ignore})

    if category.number not in categories_to_ignore:
        categories.append(category)
    return subcats

def getCategory(id):
    parsed_html = BeautifulSoup(requests.get("https://oekobox-online.eu/v3/shop/pranger/s2/C6.0.219C/category.jsp?categoryid="+str(id)+"&cartredir=1").text, features="html.parser")
    name = parsed_html.body.find(class_="font2 ic2").get_text().strip()
    existing_categories = [x for x in categories if x.number == id]
    if existing_categories:
        category = existing_categories[0]
        category.name = name
    else:
        category = base.Category(number=str(id), name=name)
    if id in categories_to_ignore:
        ignored_categories.append(category)
        return []
    else:
        if not existing_categories:
            categories.append(category)
        table = parsed_html.body.find_all('table')
        return [{"name" : name, "number" : str(id), "items" : table, "ignore" : False}]

def getIfFound(src, class_name):
    item = src.find(class_=class_name)
    text = ""
    if item and item.get_text().strip() != "" : 
        text = item.get_text().strip()
    return text

def matchCategories(name, note, category_number, cat_name):
    final_cat_name = None
    if category_number == "s51":
        if "zucker" in name:
            final_cat_name = "Zucker"
    elif category_number == "s27":
        final_cat_name = "Konserven"
    elif category_number == "s12":
        if "Essig" in name or "Essig" in note:
            final_cat_name = "Essig"
        elif "öl" in name or "Öl" in name:
            final_cat_name = "Speiseöl"
    elif category_number == "s13":
        if "honig" in name or "Honig" in note:
            final_cat_name = "Honig"
        else:
            final_cat_name = "Fruchtaufstrich"
    elif category_number == "s15":
        if "salz" in name or "Salz" in name:
            final_cat_name = "Salz"
        else:
            final_cat_name = "Gewürze"
    elif category_number == "s11" or category_number == "s32":
        if "mehl" in name or "Mehl" in name or "gemahlen" in name or "gem." in name:
            final_cat_name = "Mehl"
        elif "erbsen" in name or "Erbsen" in name or "linsen" in name or "Linsen" in name or "bohnen" in name or "Bohnen" in name:
            final_cat_name = "Hülsenfrüchte"
        elif "nüsse" in name or "Nüsse" in name:
            final_cat_name = "Nüsse"
        elif "Leinsamen" in name or "Flohsamen" in name or "Kürbiskerne" in name:
            final_cat_name = "Ölsaaten"
        else:
            final_cat_name = "Körner"
    elif category_number == "s22":
        final_cat_name = "Snacks"
    elif category_number == "s17":
        final_cat_name = "Alkoholische Getränke"
    elif category_number == "s3":
        if "kartoffel" in name or "Kartoffel" in name or "Kartoffel" in note:
            final_cat_name = "Kartoffel"
        else:
            final_cat_name = "Zwiebel, Porree, Knoblauch"
    elif category_number == "5" or category_number == "s8" or category_number == "s43" or category_number == "s44" or category_number == "s45":
        final_cat_name = "Obst"
    elif category_number == "s47":
        final_cat_name = "Milchprodukte"
    elif category_number == "2":
        final_cat_name = "Getränke"

    if final_cat_name:
        return final_cat_name
    else:
        return cat_name

def getArticles(category):
    for subcat in category:
        if subcat["items"] == [] : 
            continue
        cat_name = subcat["name"]
        ignore = subcat["ignore"]
        print(cat_name)

        for item in subcat["items"] :
            item_link = item.find(class_="font2 ic3 itemname")['href']
            item_details = BeautifulSoup(requests.get("https://oekobox-online.eu/v3/shop/pranger/s2/C6.0.222C/"+item_link).text, features="html.parser").body
            order_number = item_link.split("id=")[-1]
            if [x for x in articles if x.order_number == order_number]:
                continue
            title = item.find(class_="font2 ic3 itemname").text.replace("Bio-", "").replace(" Pkg.", "").replace(" PKG.", "").replace(" Pkg", "").replace(" PKG", "").replace(" Stk.", "").replace(" Bd.", "").replace(" Str.", "").replace(" Fl.", "").replace(" kg", "").strip()
            title_contents = re.split("(.+)\s(\d.?\d*.?\S+)\s?([a-zA-Z]*)", title)
            if len(title_contents) > 1:
                name = title_contents[1]
                if title_contents[3]:
                    name += " " + title_contents[3]
            else:
                name = title
            producer = getIfFound(item, "ic2 producer")
            note = getIfFound(item, "ic2 cinfotxt").replace("/Pkg.", "").replace(" Inhaltfüllung", "")
            origin = ""
            if producer == "Landwirtschaft Pranger" or producer == "Produktion Biohof A. Pranger e.U.":
                origin = "eigen"
            else:
                address = getIfFound(item_details, "oo-producer-address")
                if address:
                    origin = address.replace("Österreich", "").replace("AT-", "").replace("A-", "").strip()
                else:
                    origin = getIfFound(item, "herkunft")

            price_options = item.find(class_="font2 ic2 baseprice")
            prices = []
            for option in price_options.find_all("option") + price_options.find_all(class_="oo-item-price") :
                price, unit = option.get_text().strip().replace("ca. ", "").split("€/")
                new_option = PriceOption(float(price), unit)
                prices.append(new_option)

            unit_info = ""
            if len(prices) == 1:
                if len(title_contents) > 1:
                    unit_info = title_contents[2]
                elif note:
                    unit_in_note = re.split("([c]?[a]?[.]?[ ]?\d+[.,]?\d*[a-zA-Z]+)", note)
                    if len(unit_in_note) > 1:
                        unit_info = unit_in_note[1]
                        note = note.replace(unit_in_note[1], "").strip()
                if unit_info:
                    prices[0].unit = unit_info + " " + prices[0].unit

            for price in prices:
                price.unit = price.unit.replace("1kg kg", "1kg")
                if len(price.unit) > 15:
                    price.unit = price.unit.replace("Flasche", "Fl.").replace("Packung", "Pkg.").replace("Stück", "Stk")

            prices.sort(key=lambda x: x.price)
            favorite_option = None
            for option in prices:
                if option.price >= 1:
                    favorite_option = option
                    break
            if not favorite_option:
                favorite_option = prices[-1]

            item_description = getIfFound(item_details, "autohtml")
            if item_description and not item_description in note:
                if note:
                    if not note [-1] == ".":
                        note += "."
                    note += " "
                note += item_description
            loop_count = 0
            while "\n\n" in note:
                note = note.replace("\n\n", "\n")
                loop_count += 1
                if loop_count > 100:
                    print("\nLoop to replace double line breaks ran 100 times for following note:")
                    print(note)
                    break
            note = note.replace(".\n", ". ").replace("!\n", "! ").replace(";\n", "; ").replace(",\n", ", ").replace(":\n", ": ")
            note = note.replace("\n", ". ")
            loop_count = 0
            while "  " in note:
                note = note.replace("  ", " ")
                loop_count += 1
                if loop_count > 100:
                    print("\nLoop to replace double whitespaces ran 100 times for following note:")
                    print(note)
                    break

            cat_name = matchCategories(name=name, note=note, category_number=subcat["number"], cat_name=cat_name)
            article = base.Article(order_number=order_number, name=name, note=note, unit=favorite_option.unit, price_net=favorite_option.price, category=cat_name, manufacturer=producer, origin=origin, ignore=ignore, orig_unit=unit_info)
            if int(order_number) in articles_to_ignore:
                article.ignore = True
                ignored_articles.append(article)
            articles.append(article)

for idx in range(20) :
    cat = getSubcategories(idx)
    getArticles(cat)

for idx in range(20) :
    cat = getCategory(idx)
    getArticles(cat)

articles = base.remove_articles_to_ignore(articles)
articles = base.rename_duplicates(articles)
articles, notifications = base.compare_manual_changes(articles=articles, supplier=supplier, supplier_id=supplier_id, notifications=notifications)
notifications = base.write_csv(supplier=supplier, articles=articles, notifications=notifications)
base.compose_message(supplier=supplier, supplier_id=supplier_id, categories=categories, ignored_categories=ignored_categories, ignored_subcategories=ignored_subcategories, ignored_articles=ignored_articles, notifications=notifications)