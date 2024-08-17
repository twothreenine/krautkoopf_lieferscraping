class Product:
    def __init__(self, sku, name, description="", regular_price=None, category=None, attributes=None):
        """
        Partial implementation of a WooCommerce product.
        sku = unique product identification string (can include letters)
        category = ProductCategory object, limited to one.
        attributes = list of attribute dicts [{'id': 0, 'options': ['blablub']}, {...}] (options are values, usually only one in our use case)
        """
        self.sku = str(sku)
        self.name = str(name)
        self.description = str(description)
        if regular_price:
            self.regular_price = float(regular_price)
        else:
            self.regular_price = 0
        self.category = category
        if attributes:
            self.attributes = attributes
        else:
            self.attributes = {}

class ProductCategory:
    def __init__(self, name, no=None, parent=None, parent_id=None):
        self.name = name
        self.no = no
        self.parent = parent
        self.parent_id = parent_id
