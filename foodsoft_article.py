

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

class OrderArticle(Article):
    def __init__(self, amount, order_number, name, unit, price_net, total_price, unit_quantity=1):
        super().__init__(order_number=order_number, name=name, unit=unit, price_net=price_net, unit_quantity=unit_quantity)
        self.amount = amount
        self.total_price = total_price

def suffix(suffix, suffix_type=""):
    word = ""
    if suffix_type: # is this used anywhere?
        if suffix_type == "manufacturer":
            word = "von "
        elif suffix_type == "origin":
            word = "aus "
    return " (" + word + str(suffix) + ")"

def read_articles_from_csv(csv, version_delimiter=None, prefix_delimiter=None):
    articles = []
    articles_from_csv = list(csv)
    if len(articles_from_csv) > 1:
        for row in articles_from_csv[1:]:
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
            article = Article(order_number=order_number, name=row[2], note=row[3], manufacturer=row[4], origin=row[5], unit=row[6], price_net=row[7], vat=row[8], deposit=row[9], unit_quantity=row[10], category=row[13], version=version)
            articles.append(article)
    return articles
