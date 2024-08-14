import re

import base

class Article:
    def __init__(self, order_number, name, unit, price_net, available=True, note="", manufacturer="", origin="", vat=0, deposit=0, unit_quantity=1, category="", ignore=False, orig_unit="", version=1, **kwargs):
        self.available = available
        self.order_number = order_number
        self.name = str(name)
        self.note = note
        self.manufacturer = manufacturer
        self.origin = origin
        self.unit = str(unit)
        if price_net:
            self.price_net = float(price_net)
        else:
            self.price_net = 0
        if vat:
            self.vat = float(vat)
        else:
            self.vat = 0
        if deposit:
            self.deposit = float(deposit)
        else:
            self.deposit = 0
        if unit_quantity:
            self.unit_quantity = int(unit_quantity)
        else:
            self.unit_quantity = 1
        self.category = category
        self.ignore = ignore # if True, the article will not be imported
        self.orig_unit = orig_unit # Short form of article's unit, used for distinguishing duplicates, not loaded into Foodsoft
        self.version = version # number of article version
        for kwarg in kwargs: # additional variables
            setattr(self, kwarg, kwargs[kwarg])

    @property
    def price_with_vat(self):
        return self.price_net + self.price_net * self.vat / 100

    @property
    def deposit_with_vat(self):
        return self.deposit + self.deposit * self.vat / 100

    def parse_unit(self, decimal_separator=".", prefixed_currency_symbol="", postfixed_currency_symbol=" €"):
        """
        Parsing string units like "2.5 kg", "500ml", "0,5 L bottle", "1/2 dag" etc. into amount and unit (kg or l) and calculating base price.
        Strings have to consist of: number, (optional whitespace), unit symbol, (optional: whitespace + description)
        Else article.parsed_unit = None (e.g. piece articles)
        """
        unit_split_re = re.split(r'(\d+(?>,|\.|\/|\⁄?)\d*)\s?(\S*)\s?(?>.*)', self.unit)
        unit_split = [el for el in unit_split_re if el]
        unit = unit_split[-1]
        amount = None
        self.parsed_unit = None
        if len(unit_split) > 1:
            amount_str = unit_split[0].replace(",", ".")
            amount_slash_split_re = re.split(r'(\d+)(?>\/|\⁄)(\d+)', amount_str)
            amount_slash_split = [el for el in amount_slash_split_re if el]
            if len(amount_slash_split) > 1:
                numerator = int(amount_slash_split[0])
                denominator = int(amount_slash_split[1])
                amount = numerator / denominator
            else:
                try:
                    amount = float(amount_str)
                except ValueError:
                    print(f"Could not convert amount str '{amount_str}' to float ({self.name}, {self.unit})")
        else:
            amount = 1
        match unit.casefold():
            case "kg":
                unit = "kg"
            case "l" | "lt":
                unit = "l"
            case "g" | "gr":
                amount /= 1000
                unit = "kg"
            case "dag" | "dkg":
                amount /= 100
                unit = "kg"
            case "hg":
                amount /= 10
                unit = "kg"
            case "ml":
                amount /= 1000
                unit = "l"
            case "cl":
                amount /= 100
                unit = "l"
            case "dl":
                amount /= 10
                unit = "l"
            case _:
                amount = None
        if amount:
            base_price_net = self.price_net / amount
            base_price_with_vat = self.price_with_vat / amount
            base_price_with_vat_str = f"{value_with_currency_str(value=base_price_with_vat, decimal_separator=decimal_separator, prefixed_currency_symbol=prefixed_currency_symbol, postfixed_currency_symbol=postfixed_currency_symbol)} / {unit}"
            self.parsed_unit = {"amount": amount, "unit": unit, "base_price_net": base_price_net, "base_price_with_vat_str": base_price_with_vat_str}

class OrderArticle(Article):
    def __init__(self, amount, order_number, name, unit, price_net, total_price, unit_quantity=1):
        super().__init__(order_number=order_number, name=name, unit=unit, price_net=price_net, unit_quantity=unit_quantity)
        self.amount = amount
        self.total_price = total_price

class StockArticle(Article):
    def __init__(self, no, in_stock, ordered, supplier, name, unit, price_net, available=True, order_number=0, note="", vat=0, deposit=0, category=""):
        super().__init__(order_number=order_number, name=name, unit=unit, price_net=price_net, available=available, note=note, vat=vat, deposit=deposit, category=category)
        self.no = no # ID in Foodsoft
        self.in_stock = in_stock
        self.ordered = ordered
        self.supplier = supplier # foodsoft.Supplier object

def value_with_currency_str(value, decimal_separator=".", prefixed_currency_symbol="", postfixed_currency_symbol=" €", empty_if_zero=True):
    if value == 0 and empty_if_zero:
        return ""
    else:
        value_str = f"{round(value, 2):.2f}"
        return f"{prefixed_currency_symbol}{value_str.replace('.', decimal_separator)}{postfixed_currency_symbol}"

def suffix(suffix, suffix_type=""):
    word = ""
    if suffix_type: # is this used anywhere?
        if suffix_type == "manufacturer":
            word = "von "
        elif suffix_type == "origin":
            word = "aus "
    return " (" + word + str(suffix) + ")"

def read_articles_from_csv(csv, version_delimiter=None, prefix_delimiter=None, skip_unavailable_articles=False):
    articles = []
    articles_from_csv = list(csv)
    if len(articles_from_csv) > 1:
        for row in articles_from_csv[1:]:
            avail_str = row[0]
            # yes_strs = ['Yes', 'Ja', 'Sí', 'Oui', 'Ja', 'Evet'] # not needed (yet)
            no_strs = ['No', 'Nein', 'No', 'Non', 'Nee'] # en, de, es, fr, ne, (tr only yes)
            if base.equal_strings_check(list1=[avail_str], list2=no_strs):
                available = False
                if skip_unavailable_articles:
                    continue
            else:
                available = True
            order_number = row[1]
            version = 1
            if version_delimiter:
                order_number_strings = order_number.split(version_delimiter)
                if len(order_number_strings) > 1:
                    order_number = version_delimiter.join(order_number_strings[:-1])
                    version = int(order_number_strings[-1])
            if prefix_delimiter:
                order_number_strings = order_number.split(prefix_delimiter)
                if len(order_number_strings) > 1:
                    order_number = prefix_delimiter.join(order_number_strings[1:])
            article = Article(order_number=order_number, name=row[2], note=row[3], manufacturer=row[4], origin=row[5], unit=row[6], price_net=row[7], available=available, vat=row[8], deposit=row[9], unit_quantity=row[10], category=row[13], version=version)
            articles.append(article)
    return articles
