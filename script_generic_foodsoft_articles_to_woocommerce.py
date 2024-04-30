"""
Collects all articles from your Foodsoft instance and imports them into WooCommerce via API. Useful for creating a public product catalog.
In case you want to exclude certain suppliers, you can do that by using supplier categories in Foodsoft.
"""

import importlib
import re
import math
import html
import requests
import time
import woocommerce

import base
import foodsoft
import foodsoft_article
import foodsoft_article_import
import woocommerce_product

# Inputs this script's methods take
consumer_key = base.Input(name="consumer_key", required=True, input_format="text", example="ck_123")
consumer_secret = base.Input(name="consumer_secret", required=True, input_format="password", example="cs_123")

# Executable script methods
collect_products_and_import_to_woocommerce = base.ScriptMethod(name="collect_products_and_import_to_woocommerce", inputs=[consumer_key, consumer_secret])
collect_products = base.ScriptMethod(name="collect_products")
import_to_woocommerce = base.ScriptMethod(name="import_to_woocommerce", inputs=[consumer_key, consumer_secret])

def config_variables(): # List of the special config variables this script uses, whether they are required and how they could look like
    return [
        base.Variable(name="website URL", required=True, example="https://example.com", description="WooCommerce website as target for product import"),
        base.Variable(name="supplier name prefix delimiters", required=False, example=[') ', '] ']),
        base.Variable(name="supplier name suffix delimiters", required=False, example=[' (', ' [']),
        base.Variable(name="category name prefix delimiters", required=False, example=[') ', '] ']),
        base.Variable(name="category name suffix delimiters", required=False, example=[' (', ' [']),
        base.Variable(name="exclude supplier categories", required=False, example=['inactive', 'dummy']),
        base.Variable(name="supplier name field(s)", required=False, example=['custom_fields_public_name', 'name'], description="List of fields which should be checked and used as supplier name if not empty"),
        base.Variable(name="supplier origin field(s)", required=False, example=['custom_fields_origin'], description="List of fields which should be checked and used as supplier origin if not empty"),
        base.Variable(name="replace articles origin with supplier origin", required=False, example=['', 'own'], description="List of article origin strings that should be replaced by supplier origin"),
        base.Variable(name="use supplier as manufacturer for stock articles", required=False, example=True, description="True/False whether stock articles' manufacturer attribute should be filled with supplier name or be left empty"),
        base.Variable(name="supplier custom field for whether replacing articles manufacturer if empty (replace if field not empty)", required=False, example="self_produced_if_manufacturer_empty", description="Checks for a custom field of the specified name and if the value isn't an empty string, articles of this supplier with manufacturer field empty will be considered produced by the supplier itself"), # TODO: replace by custom boolean field in Foodsoft - didn't know how to set the value to true via database
        base.Variable(name="super categories", required=False, example={'Fresh goods': {'exact': ['Fruits']}}, description="Super categories which a list of categories from Foodsoft should be sorted into -- supported matching algorithms: 'exact', 'containing', 'startswith', 'endswith'; optionally use 'omit category': true to omit the subcategory."),
        base.Variable(name="regex for categories", required=False, example='(?>[(][a-z][)] )?(.*)', description="Regular expression that should be applied to change a category's name (after super category sorting), taking first captured group."),
        base.Variable(name="regex for splitting article name into name and base price", required=False, example='(.*)(?>\s\()(\d\d?(?>\,|\.)?\d*\s?\€\s?\/\s?.*)(?>\))', description="Regular expression that should be applied to split name, e.g. 'Carrots (2.00 €/kg)'"),
        base.Variable(name="regex for splitting stock article name into order number and name", required=False, example='(\d+.*)(?>\s\()(.*)(?>\))', description="Regular expression that should be applied to split stock article name, e.g. '001test (Test article)'"),
        base.Variable(name="omit stock article categories", required=False, example=["Other"], description="List of category names of which stock articles should be omitted"),
        base.Variable(name="decimal separator", required=False, example=",", description="use . or , as decimal separator for numbers"),
        base.Variable(name="prefixed currency symbol", required=False, example="EUR ", description="include whitespace if needed"),
        base.Variable(name="postfixed currency symbol", required=False, example=" €", description="include whitespace if needed"),
        # base.Variable(name="supplier address field(s)", required=False, example=['custom_fields_public_address', 'address'], description="List of fields which should be checked and used as supplier address if not empty"),
        # base.Variable(name="supplier website field(s)", required=False, example=['custom_fields_public_homepage', 'url'], description="List of fields which should be checked and used as supplier website link if not empty"),
        base.Variable(name="supplier category field(s)", required=False, example=['supplier_category_id'], description="List of fields (select!) which should be checked and used as supplier category if not empty"),
        base.Variable(name="additional supplier field(s)", required=False, example=[{'foodsoft field(s)': ['custom_fields_ordering_cycle'], 'id': 6}], description="Other supplier info which should be added under the specified global attribute id"),
        base.Variable(name="id of unit attribute", required=False, example=0, description="id of global attribute in WooCommerce"),
        base.Variable(name="id of base price attribute", required=False, example=1, description="id of global attribute in WooCommerce"),
        base.Variable(name="id of supplier attribute", required=False, example=2, description="id of global attribute in WooCommerce"),
        base.Variable(name="id of origin attribute", required=False, example=3, description="id of global attribute in WooCommerce"),
        base.Variable(name="id of manufacturer attribute", required=False, example=4, description="id of global attribute in WooCommerce"),
        base.Variable(name="id of deposit attribute", required=False, example=5, description="id of global attribute in WooCommerce"),
        base.Variable(name="id of stock article attribute", required=False, example=6, description="id of global attribute in WooCommerce"),
        base.Variable(name="value of stock article attribute", required=False, example="Stock article", description="Text that should appear in the specified attribute if article is a stock article"),
        base.Variable(name="resort stock articles into categories", required=False, example=True, description="True/False whether stock articles should be resorted into article categories from Foodsoft (category names containing, keywords exact matches)"),
        base.Variable(name="unit suffix when unit quantity greater than 1", required=False, example=" (as part of a pack of {unit_quantity}", description="Text that should be added to the unit, containing the keyword unit_quantity in brackets to be replaced by the unit quantity number")
        ]

class ScriptRun(base.Run):
    def __init__(self, foodcoop, configuration):
        super().__init__(foodcoop=foodcoop, configuration=configuration)
        self.next_possible_methods = [collect_products_and_import_to_woocommerce, collect_products]

    def collect_products_and_import_to_woocommerce(self, session, consumer_key, consumer_secret):
        self.collect_products(session=session)
        self.import_to_woocommerce(session=session, consumer_key=consumer_key, consumer_secret=consumer_secret)

    def collect_products(self, session):
        config = base.read_config(self.foodcoop, self.configuration)
        additional_supplier_fields = config.get("additional supplier field(s)", [])
        supplier_custom_field_for_whether_replacing_articles_manufacturer_if_empty = config.get("supplier custom field for whether replacing articles manufacturer if empty")
        if supplier_custom_field_for_whether_replacing_articles_manufacturer_if_empty:
            additional_supplier_fields.append({'foodsoft field(s)': [supplier_custom_field_for_whether_replacing_articles_manufacturer_if_empty]})
        name_fields = config.get("supplier name field(s)", [])
        category_fields = config.get("supplier category field(s)", [])
        origin_fields = config.get("supplier origin field(s)", [])
        exclude_categories = config.get("exclude supplier categories", [])
        supplier_name_prefix_delimiters = config.get("supplier name prefix delimiters", [])
        supplier_name_suffix_delimiters = config.get("supplier name suffix delimiters", [])
        category_name_prefix_delimiters = config.get("category name prefix delimiters", [])
        category_name_suffix_delimiters = config.get("category name suffix delimiters", [])
        replace_articles_origin_with_supplier_origin = config.get("replace articles origin with supplier origin", [])
        super_categories = config.get("super categories", {})
        regex_for_categories = config.get("regex for categories", "")
        regex_for_splitting_article_name_into_name_and_base_price = config.get("regex for splitting article name into name and base price", "")
        regex_for_splitting_stock_article_name_into_order_number_and_name = config.get("regex for splitting stock article name into order number and name", "")
        omit_stock_article_categories = config.get("omit stock article categories", [])
        decimal_separator = config.get("decimal separator", ".")
        prefixed_currency_symbol = config.get("prefixed currency symbol", "")
        postfixed_currency_symbol = config.get("postfixed currency symbol", " €")
        id_of_stock_article_attribute = config.get("id of stock article attribute", None)
        value_of_stock_article_attribute = config.get("value of stock article attribute", "")
        unit_suffix_when_unit_quantity_greater_than_1 = config.get("unit suffix when unit quantity greater than 1", "")

        suppliers = session.foodsoft_connector.get_supplier_data(name_fields=name_fields, origin_fields=origin_fields, category_fields=category_fields, additional_fields=additional_supplier_fields, exclude_categories=exclude_categories)
        self.article_categories = session.foodsoft_connector.get_article_categories()

        self.products = []
        self.product_categories = []
        self.notifications = []

        for supplier in suppliers:
            supplier.apply_supplier_delimiters(supplier_name_prefix_delimiters=supplier_name_prefix_delimiters, supplier_name_suffix_delimiters=supplier_name_suffix_delimiters, category_name_prefix_delimiters=category_name_prefix_delimiters, category_name_suffix_delimiters=category_name_suffix_delimiters)
            supplier_articles, self.notifications = foodsoft_article_import.get_articles_from_foodsoft(locales=session.locales, supplier_id=supplier.no, foodsoft_connector=session.foodsoft_connector, skip_unavailable_articles=True, notifications=self.notifications)
            for s_a in supplier_articles:
                if s_a.origin in replace_articles_origin_with_supplier_origin and supplier.origin:
                    s_a.origin = supplier.origin
                article = replace_article_manufacturer(article=s_a, supplier=supplier, supplier_custom_field_for_whether_replacing_articles_manufacturer_if_empty=supplier_custom_field_for_whether_replacing_articles_manufacturer_if_empty)
                if not s_a.order_number:
                    s_a.order_number = f"article{str(supplier_articles.index(s_a))}"
                sku = f"{supplier.no}_{s_a.order_number}"
                name, base_price = self.split_article_name_into_name_and_base_price(article_name=s_a.name, supplier_name=supplier.name, regex_for_splitting_article_name_into_name_and_base_price=regex_for_splitting_article_name_into_name_and_base_price)
                category = self.categorize(original_category_name=s_a.category, article_name=name, super_categories=super_categories, regex_for_categories=regex_for_categories)
                if not base_price:
                    s_a.parse_unit(decimal_separator=decimal_separator, prefixed_currency_symbol=prefixed_currency_symbol, postfixed_currency_symbol=postfixed_currency_symbol)
                    if s_a.parsed_unit:
                        base_price = s_a.parsed_unit.get("base_price_with_vat_str")
                if unit_suffix_when_unit_quantity_greater_than_1 and s_a.unit_quantity > 1:
                    s_a.unit += unit_suffix_when_unit_quantity_greater_than_1.format(unit_quantity=str(s_a.unit_quantity))
                attributes = [
                    {'id': config.get("id of unit attribute", 0), 'options': [s_a.unit]},
                    {'id': config.get("id of base price attribute", 1), 'options': [base_price]},
                    {'id': config.get("id of supplier attribute", 2), 'options': [supplier.name]},
                    {'id': config.get("id of origin attribute", 3), 'options': [s_a.origin]},
                    {'id': config.get("id of manufacturer attribute", 4), 'options': [s_a.manufacturer]},
                    {'id': config.get("id of deposit attribute", 5), 'options': [foodsoft_article.value_with_currency_str(value=s_a.deposit_with_vat, decimal_separator=decimal_separator, prefixed_currency_symbol=prefixed_currency_symbol, postfixed_currency_symbol=postfixed_currency_symbol)]}
                ]
                for supplier_field in supplier.additional_fields:
                    if supplier_field.get("id"):
                        attributes.append({'id': supplier_field.get("id"), 'options': [supplier_field.get("value")]})

                product = woocommerce_product.Product(sku=sku, name=name, regular_price=round(s_a.price_with_vat, 2), category=category, attributes=attributes, description=s_a.note)
                self.products.append(product)

        stock_articles_from_foodsoft, suppliers = session.foodsoft_connector.get_stock_articles_and_suppliers(skip_unavailable_articles=True, suppliers=suppliers, name_fields=name_fields, category_fields=category_fields, origin_fields=origin_fields, additional_fields=additional_supplier_fields, exclude_categories=omit_stock_article_categories)
        for supplier in suppliers:
            supplier.apply_supplier_delimiters(supplier_name_prefix_delimiters=supplier_name_prefix_delimiters, supplier_name_suffix_delimiters=supplier_name_suffix_delimiters, category_name_prefix_delimiters=category_name_prefix_delimiters, category_name_suffix_delimiters=category_name_suffix_delimiters)
        stock_products = []
        for saff in stock_articles_from_foodsoft:
            name_split_re = re.split(regex_for_splitting_stock_article_name_into_order_number_and_name, saff.name)
            name_split = [el for el in name_split_re if el]
            if len(name_split) > 1:
                sku = name_split[0]
                name = name_split[1]
                if len(name_split) > 2:
                    rest = "".join(name_split[2:])
                    self.notifications.append(f"Article name '{saff.name}' (stock article) split into more than 2 parts: '{order_number}' (order number), '{name}' (name), and '{rest}' (ignored rest)")
            else:
                name = saff.name
                sku = saff.order_number
            name, base_price = self.split_article_name_into_name_and_base_price(article_name=name, supplier_name=saff.supplier.name, regex_for_splitting_article_name_into_name_and_base_price=regex_for_splitting_article_name_into_name_and_base_price)
            if name in [sp.name for sp in stock_products if sp.attributes[2].get("options")[0] == saff.supplier.name]: # TODO: find a better way to omit supply duplicates (e.g. marking them in Foodsoft)
                continue
            saff.supplier.apply_supplier_delimiters(supplier_name_prefix_delimiters=supplier_name_prefix_delimiters, supplier_name_suffix_delimiters=supplier_name_suffix_delimiters, category_name_prefix_delimiters=category_name_prefix_delimiters, category_name_suffix_delimiters=category_name_suffix_delimiters)
            if config.get("use supplier as manufacturer for stock articles"):
                manufacturer = saff.supplier.name
            else:
                manufacturer = ""
            if saff.origin in replace_articles_origin_with_supplier_origin and saff.supplier.origin:
                origin = saff.supplier.origin
            else:
                origin = ""
            saff = replace_article_manufacturer(article=saff, supplier=saff.supplier, supplier_custom_field_for_whether_replacing_articles_manufacturer_if_empty=supplier_custom_field_for_whether_replacing_articles_manufacturer_if_empty)
            if config.get("resort stock articles into categories"):
                for ac in self.article_categories:
                    if base.containing_strings_check(list1=[name], list2=[ac.name]) or base.equal_strings_check(list1=[name], list2=ac.keywords):
                        saff.category = ac.name
            category = self.categorize(original_category_name=saff.category, article_name=name, super_categories=super_categories, regex_for_categories=regex_for_categories)
            if not base_price:
                saff.parse_unit(decimal_separator=decimal_separator, prefixed_currency_symbol=prefixed_currency_symbol, postfixed_currency_symbol=postfixed_currency_symbol)
                if saff.parsed_unit:
                    base_price = saff.parsed_unit.get("base_price_with_vat_str")
            attributes = [
                {'id': config.get("id of unit attribute", 0), 'options': [saff.unit]},
                {'id': config.get("id of base price attribute", 1), 'options': [base_price]},
                {'id': config.get("id of supplier attribute", 2), 'options': [saff.supplier.name]},
                {'id': config.get("id of origin attribute", 3), 'options': [origin]},
                {'id': config.get("id of manufacturer attribute", 4), 'options': [manufacturer]},
                {'id': config.get("id of deposit attribute", 5), 'options': [foodsoft_article.value_with_currency_str(value=saff.deposit_with_vat, decimal_separator=decimal_separator, prefixed_currency_symbol=prefixed_currency_symbol, postfixed_currency_symbol=postfixed_currency_symbol)]}
            ]
            for supplier_field in saff.supplier.additional_fields:
                if supplier_field.get("id"):
                    attributes.append({'id': supplier_field.get("id"), 'options': [supplier_field.get("value")]})
            if id_of_stock_article_attribute:
                for attr in attributes:
                    if attr.get("id") == id_of_stock_article_attribute:
                        attr["options"] = [value_of_stock_article_attribute]
                        break
                attributes.append({"id": id_of_stock_article_attribute, "options": [value_of_stock_article_attribute]})

            product = woocommerce_product.Product(sku=sku, name=name, regular_price=round(saff.price_with_vat, 2), category=category, attributes=attributes, description=saff.note)
            stock_products.append(product)

        number_of_order_products = len(self.products)
        self.products = stock_products + self.products

        self.message = session.locales["generic_foodsoft_articles_to_woocommerce"]["collected products summary"].format(number_of_collected_products=str(len(self.products)), number_of_suppliers=str(len(suppliers)), number_of_order_products=str(number_of_order_products), number_of_stock_products=str(len(stock_products)))
        base.write_txt(file_path=base.file_path(path=self.path, folder="display", file_name=session.locales["base"]["summary"]), content=self.message)
        self.log.append(base.LogEntry(action="products collected", done_by=base.full_user_name(session)))
        self.next_possible_methods = [import_to_woocommerce]
        self.completion_percentage = 50

    def import_to_woocommerce(self, session, consumer_key, consumer_secret):
        config = base.read_config(self.foodcoop, self.configuration)
        manual_changes_for_products = config.get("manual changes for products", {})
        if not manual_changes_for_products:
            config["manual changes for products"] = {}
        woocommerce_API = woocommerce.API(url=config.get("website URL"), consumer_key=consumer_key, consumer_secret=consumer_secret)

        product_categories_from_woocommerce_json = self.batch_retrieve(api=woocommerce_API, endpoint="products/categories")
        for pc in product_categories_from_woocommerce_json:
            pc["name"] = html.unescape(pc.get("name"))
            # pc_index = product_categories_from_woocommerce_json.index(pc)
            # product_categories_from_woocommerce_json[pc_index]["name"] = html.unescape(pc.get("name"))
        product_categories_from_woocommerce = []
        for pc in product_categories_from_woocommerce_json:
            print(pc.get("id"), pc.get("name"), pc.get("parent"))
            product_categories_from_woocommerce.append(woocommerce_product.ProductCategory(name=pc.get("name"), no=pc.get("id"), parent_id=pc.get("parent")))
        for pc in product_categories_from_woocommerce:
            if pc.parent_id:
                pc.parent = next((mc for mc in product_categories_from_woocommerce if mc.no == pc.parent_id), None)

        products_from_woocommerce_json = self.batch_retrieve(api=woocommerce_API, endpoint="products")
        for p in products_from_woocommerce_json:
            p["name"] = html.unescape(p.get("name"))
            p["description"] = html.unescape(p.get("description"))
            p["sku"] = html.unescape(p.get("sku"))
            for attr in p.get("attributes"):
                unescaped_options = [html.unescape(option) for option in attr.get("options")]
                attr["options"] = unescaped_options
        products_from_woocommerce = []
        for p in products_from_woocommerce_json:
            p_category = None
            p_c = p.get("categories")
            if p_c:
                p_c_id = p_c[0].get("id")
                matching_categories = [pc for pc in product_categories_from_woocommerce if pc.no == p_c_id]
                p_category = matching_categories[0]
            pfw = woocommerce_product.Product(sku=p.get("sku"), name=p.get("name"), description=p.get("description"), regular_price=p.get("regular_price"), category=p_category, attributes=p.get("attributes"))
            pfw.no = p.get("id")
            products_from_woocommerce.append(pfw)

        last_imported_run_name = config.get("last imported run")
        products_from_last_run = []
        product_categories_from_last_run = []
        if last_imported_run_name:
            last_imported_run_path, self.notifications = base.get_file_path(foodcoop=self.foodcoop, configuration=self.configuration, run=last_imported_run_name, folder="", ending="", notifications=self.notifications)
            last_imported_run = self.load(last_imported_run_path)
            products_from_last_run = last_imported_run.products
            product_categories_from_last_run = last_imported_run.product_categories
        
        product_categories_to_create = []
        product_categories_to_update = []
        for pc in self.product_categories:
            if not pc.name:
                print(f"Skipping product category:")
                for p in [pr for pr in self.products if pr.category == pc]:
                    print(p.sku, p.name)
                print("")
                continue
            pc_wc = next((c for c in product_categories_from_woocommerce if c.name == pc.name), None)
            if pc_wc:
                pc.no = pc_wc.no
                if (pc.parent and not pc_wc.parent) or (not pc.parent and pc_wc.parent) or (pc.parent and pc_wc.parent and pc.parent.name != pc_wc.parent.name):
                    product_categories_to_update.append(pc)
            else:
                product_categories_to_create.append(pc)

        pcs_without_parent = [pc for pc in product_categories_to_create if not pc.parent]
        pcs_without_parent_batch_create = [{"name": pc.name} for pc in pcs_without_parent]
        for pc in pcs_without_parent_batch_create:
            print(pc)
        response_data = self.batch_update(api=woocommerce_API, endpoint="products/categories/batch", method="create", data=pcs_without_parent_batch_create)
        for pc in pcs_without_parent:
            print(pc.no, pc.name)
            pc.no = next((c.get("id") for c in response_data if c.get("name") == pc.name))

        pcs_with_parent = [pc for pc in product_categories_to_create if pc not in pcs_without_parent]
        pcs_with_parent_batch_create = [{"name": pc.name, "parent": pc.parent.no} for pc in pcs_with_parent]
        response_data = self.batch_update(api=woocommerce_API, endpoint="products/categories/batch", method="create", data=pcs_with_parent_batch_create)
        for pc in pcs_with_parent:
            print(pc.no, pc.name, pc.parent.no)
            pc.no = next((c.get("id") for c in response_data if c.get("name") == pc.name))

        pc_batch_update = []
        for pc in product_categories_to_update:
            if pc.parent:
                parent = pc.parent.no
            else:
                parent = 0
            pc_batch_update.append({"id": pc.no, "name": pc.name, "parent": parent})
        self.batch_update(api=woocommerce_API, endpoint="products/categories/batch", method="update", data=pc_batch_update)

        pc_batch_delete = [pc_wc.no for pc_wc in product_categories_from_woocommerce if pc_wc.name not in [pc.name for pc in self.product_categories]]
        self.batch_update(api=woocommerce_API, endpoint="products/categories/batch", method="delete", data=pc_batch_delete)

        for p in self.products:
            if p.category:
                p.category_id = p.category.no
            else:
                p.category_id = None

        products_to_create_json = [product_to_dict(p) for p in self.products if p.sku not in [wcp.get("sku") for wcp in products_from_woocommerce_json]]
        products_to_delete_json = []
        products_to_keep = []
        kept_products_skus = []
        for pfw in products_from_woocommerce:
            matching_product = next((p for p in self.products if p.sku == pfw.sku), None)
            if matching_product and pfw.sku not in kept_products_skus: # only keep if pfw isn't a duplicate
                matching_product.no = pfw.no
                products_to_keep.append(matching_product)
                kept_products_skus.append(pfw.sku)
            else:
                products_to_delete_json.append(pfw.no)

        self.products_to_update = []
        for p in products_to_keep:
            p_last = next((pr for pr in products_from_last_run if pr.sku == p.sku), None)
            p_wc = next((pr for pr in products_from_woocommerce if pr.sku == p.sku), None)
            p_mc = manual_changes_for_products.get(p.sku, {})
            for attribute in ["name", "description", "regular_price", "attributes", "category_id"]:
                config, p, p_mc = self.compare_values(locales=session.locales, config=config, product=p, product_from_last_run=p_last, product_from_woocommerce=p_wc, manual_changes_for_product=p_mc, attribute=attribute)
            p.category = next((pc for pc in self.product_categories if pc.no == p.category_id), None)

        self.batch_update(api=woocommerce_API, endpoint="products/batch", method="delete", data=products_to_delete_json)
        self.batch_update(api=woocommerce_API, endpoint="products/batch", method="create", data=products_to_create_json)

        products_to_update_json = []
        for p in self.products_to_update:
            p_dict = {"id": p.no} | product_to_dict(p)
            products_to_update_json.append(p_dict)
        self.batch_update(api=woocommerce_API, endpoint="products/batch", method="update", data=products_to_update_json)

        self.message += "\n\n" + session.locales["generic_foodsoft_articles_to_woocommerce"]["updated categories summary"].format(number_of_created_categories=str(len(product_categories_to_create)), number_of_updated_categories=str(len(product_categories_to_update)), number_of_deleted_categories=str(len(pc_batch_delete)))
        self.message += "\n" + session.locales["generic_foodsoft_articles_to_woocommerce"]["updated products summary"].format(number_of_created_products=str(len(products_to_create_json)), number_of_updated_products=str(len(self.products_to_update)), number_of_deleted_products=str(len(products_to_delete_json)))
        if self.notifications:
            self.message += f'\n\n{session.locales["base"]["notifications"]}:'
            for notification in self.notifications:
                self.message += f"\n- {notification}"
        base.write_txt(file_path=base.file_path(path=self.path, folder="display", file_name=session.locales["base"]["summary"]), content=self.message)

        base.set_config_detail(foodcoop=self.foodcoop, configuration=self.configuration, detail="last imported run", value=self.name)
        base.set_config_detail(foodcoop=self.foodcoop, configuration=self.configuration, detail="manual changes for products", value=manual_changes_for_products)
        self.log.append(base.LogEntry(action="imported to woocommerce", done_by=base.full_user_name(session)))
        self.next_possible_methods = []
        self.completion_percentage = 100

    def split_article_name_into_name_and_base_price(self, article_name, supplier_name, regex_for_splitting_article_name_into_name_and_base_price):
        name_split_re = re.split(regex_for_splitting_article_name_into_name_and_base_price, article_name)
        name_split = [el for el in name_split_re if el]
        if len(name_split) > 1:
            name = name_split[0]
            base_price = name_split[1]
            if len(name_split) > 2:
                rest = " ".join(name_split[2:])
                name += f" {rest}"
                # self.notifications.append(f"Article name '{article_name}' ({supplier_name}) split into more than 2 parts: '{name}' (name), '{base_price}' (base price), and '{rest}' (ignored rest)")
        else:
            name = article_name
            base_price = ""
        return name, base_price

    def categorize(self, original_category_name, article_name, super_categories, regex_for_categories=""):
        category_name = original_category_name
        super_category_name = ""
        # category_number = self.find_article_category_number(original_category_name)
        for sc_name, sc_details in super_categories.items():
            if base.equal_strings_check(list1=[category_name], list2=sc_details.get("exact", [])):
                super_category_name, category_name = self.apply_super_category_name(category_name=category_name, sc_name=sc_name, sc_details=sc_details)
            elif base.containing_strings_check(list1=[category_name], list2=sc_details.get("containing", [])):
                super_category_name, category_name = self.apply_super_category_name(category_name=category_name, sc_name=sc_name, sc_details=sc_details)
            elif base.startswith_strings_check(list1=[category_name], list2=sc_details.get("startswith", [])):
                super_category_name, category_name = self.apply_super_category_name(category_name=category_name, sc_name=sc_name, sc_details=sc_details)
            elif base.endswith_strings_check(list1=[category_name], list2=sc_details.get("endswith", [])):
                super_category_name, category_name = self.apply_super_category_name(category_name=category_name, sc_name=sc_name, sc_details=sc_details)
        if regex_for_categories:
            regex = re.search(regex_for_categories, category_name)
            if regex:
                category_name = regex.group(1)
        matching_categories = [c for c in self.product_categories if c.name == category_name]
        if matching_categories:
            cat = matching_categories[0]
        else:
            cat = woocommerce_product.ProductCategory(name=category_name)
            self.product_categories.append(cat)
        if super_category_name:
            super_cat = next((c for c in self.product_categories if c.name == super_category_name), None)
            if not super_cat:
                super_cat = woocommerce_product.ProductCategory(name=super_category_name)
                self.product_categories.append(super_cat)
                print("Added super category with name: ", super_category_name)
            cat.parent = super_cat
        return cat

    def find_article_category_number(self, category_name):
        matching_categories = [c for c in self.article_categories if c.name == category_name]
        if matching_categories:
            return matching_categories[0].number

    def apply_super_category_name(self, category_name, sc_name, sc_details):
        if sc_details.get("omit category"):
            category_name = sc_name
            super_category_name = None
        else:
            super_category_name = sc_name
        return super_category_name, category_name

    def compare_values(self, locales, config, product, product_from_last_run, product_from_woocommerce, manual_changes_for_product, attribute):
        mc_attribute = manual_changes_for_product.get(attribute, {})
        attr_from_last_run = getattr(product_from_last_run, attribute, None)
        attr_from_woocommerce = getattr(product_from_woocommerce, attribute, None)
        current_attr = getattr(product, attribute, None)
        if (attr_from_last_run == current_attr) and (attr_from_last_run != attr_from_woocommerce):
            if not manual_changes_for_product:
                config["manual changes for products"][product.sku] = {}
            config["manual changes for products"][product.sku][attribute] = {"replaced": attr_from_last_run, "manual": attr_from_woocommerce}
            self.notifications.append(locales["generic_foodsoft_articles_to_woocommerce"]["keeping manual change"].format(article_number=product.sku, article_name=product.name, string_type=attribute, replaced_string=attr_from_last_run, manual_string=attr_from_woocommerce))
            setattr(product, attribute, attr_from_woocommerce)
        else:
            if mc_attribute and current_attr == mc_attribute.get("replaced"):
                setattr(product, attribute, mc_attribute.get("manual"))
            if getattr(product, attribute, None) != attr_from_woocommerce and product not in self.products_to_update:
                self.products_to_update.append(product)

        p_mc = manual_changes_for_product.get(product.sku, {})
        return config, product, p_mc

    def batch_retrieve(self, api, endpoint):
        data = []
        response = True
        page = 1
        print(f"\nStarting batch retrieve: {endpoint}")
        while response:
            for i in range(25):
                try:
                    response = api.get(f"{endpoint}?page={str(page)}&per_page=50").json()
                    break
                except requests.exceptions.ReadTimeout:
                    if i < 24:
                        print("requests.exceptions.ReadTimeout, waiting 5 seconds and trying again ...")
                        time.sleep(5)
                    else:
                        print("requests.exceptions.ReadTimeout error for 25 times in a row - raising error")
                        raise
            data.extend(response)
            page += 1
        return data

    def batch_update(self, api, endpoint, method, data):
        response_data = []
        print(f"\nStarting batch {method}: {endpoint}")
        while data:
            chunk, data = data[:10], data[10:]
            for el in chunk:
                print(el)
            for i in range(25):
                try:
                    response_data.extend(api.post(endpoint, {method: chunk}).json().get(method))
                    break
                except requests.exceptions.ReadTimeout:
                    if i < 24:
                        print("requests.exceptions.ReadTimeout, waiting 5 seconds and trying again ...")
                        time.sleep(5)
                    else:
                        print("requests.exceptions.ReadTimeout error for 25 times in a row - raising error")
                        raise
        for rd in response_data:
            print(f"id: {rd.get('id')}, name: {rd.get('name')}")
        return response_data

def product_to_dict(product):
    return {"sku": product.sku, "name": product.name, "description": product.description, "regular_price": product.regular_price, "categories": [{"id": product.category.no}], "attributes": product.attributes}

def replace_article_manufacturer(article, supplier, supplier_custom_field_for_whether_replacing_articles_manufacturer_if_empty):
    if not article.manufacturer and supplier_custom_field_for_whether_replacing_articles_manufacturer_if_empty and next((af for af in supplier.additional_fields if af.get('foodsoft field(s)') == supplier_custom_field_for_whether_replacing_articles_manufacturer_if_empty), False):
        article.manufacturer = supplier.name
    return article

if __name__ == "__main__":
    importlib.invalidate_caches()
    script = importlib.import_module("script_generic_foodsoft_articles_to_woocommerce") # I don't know why we have to do this, but if the ScriptRun object is just initialized directly (run = ScriptRun(...)), then it doesn't load when we try to load in web ("AttributeError: Can't get attribute 'ScriptRun' on <module '__main__' from 'web.py'>")
    run = script.ScriptRun(foodcoop="krautkoopf", configuration="Produktkatalog")
    while run.next_possible_methods:
        func = getattr(run, run.next_possible_methods[0].name)
        func()
    run.save()
