"""
Script for creating one or multiple Foodsoft orders for one supplier with fewer clicks, with the option of sending out a Foodsoft message to all members.
"""

import importlib
import datetime
import time
import babel.dates
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager

import base
import foodsoft_article
import foodsoft_article_import

# Inputs this script's methods take
create_orders_till = base.Input(name="create_orders_till", required=False, input_format="date")
create_orders_from = base.Input(name="create_orders_from", required=False, input_format="date")
number_of_orders_to_create = base.Input(name="number_of_orders_to_create", required=False, input_format="number")
message_subject_suffix = base.Input(name="message_subject_suffix", required=False)
message_extra_content = base.Input(name="message_extra_content", required=False, input_format="textarea")

# Executable script methods
create_orders_directly = base.ScriptMethod(name="create_orders_directly", inputs=[create_orders_till, create_orders_from, number_of_orders_to_create, message_subject_suffix, message_extra_content])
prepare_orders = base.ScriptMethod(name="prepare_orders", inputs=[create_orders_till, create_orders_from, number_of_orders_to_create])
create_prepared_orders = base.ScriptMethod(name="create_prepared_orders", inputs=[message_subject_suffix, message_extra_content])

def config_variables(): # List of the special config variables this script uses, whether they are required and how they could look like
    return [
        base.Variable(name="Foodsoft supplier ID", required=True, example=12),
        # base.Variable(name="allow simultaneous orders", required=False, example=False),
        base.Variable(name="min interval", required=False, example=1, description="between order ends, in days"),
        base.Variable(name="order start time", required=False, example="00:00"),
        base.Variable(name="order end weekdays", required=False, example="wednesday;saturday"),
        base.Variable(name="order end time", required=False, example="23:59"),
        base.Variable(name="min order duration", required=False, example=1),
        base.Variable(name="max order duration", required=False, example=6),
        base.Variable(name="delivery duration", required=False, example=6),
        base.Variable(name="auto close", required=False, example=True),
        base.Variable(name="auto send", required=False, example=True),
        base.Variable(name="ignore minimum quantity", required=False, example=False),
        base.Variable(name="note", required=False, example="This text will be shown as the order note"),
        base.Variable(name="send message", required=False, example=True),
        base.Variable(name="message subject", required=False, example="New order open"),
        base.Variable(name="message content top", required=False, example="Hi all, you can place your order now."),
        base.Variable(name="message content bottom", required=False, example="Greets, your pseudo-human")
        ]

class ScriptRun(base.Run):
    def __init__(self, foodcoop, configuration):
        super().__init__(foodcoop=foodcoop, configuration=configuration)
        self.next_possible_methods = [create_orders_directly, prepare_orders]

    def create_orders_directly(self, session, create_orders_till=None, create_orders_from=None, number_of_orders_to_create=1, message_subject_suffix="", message_extra_content=""):
        self.prepare_orders(session=session, create_orders_till=create_orders_till, create_orders_from=create_orders_from, number_of_orders_to_create=number_of_orders_to_create)
        self.create_prepared_orders(session=session, message_subject_suffix=message_subject_suffix, message_extra_content=message_extra_content)

    def prepare_orders(self, session, create_orders_till=None, create_orders_from=None, number_of_orders_to_create=1):
        config = base.read_config(self.foodcoop, self.configuration)
        self.supplier_id = config.get("Foodsoft supplier ID")
        # allow_simultaneous_orders = config.get("allow simultaneous orders")
        min_interval = config.get("min interval", 1)
        start_time = time.strptime(config.get("order start time", "00:00"), "%H:%M")
        end_weekdays = config.get("order end weekdays").split(";")
        end_time = time.strptime(config.get("order end time", "23:59"), "%H:%M")
        min_order_duration = config.get("min order duration", 0)
        max_order_duration = config.get("max order duration")
        delivery_duration = config.get("delivery duration")
        auto_close = config.get("auto close")
        auto_send = config.get("auto send")
        ignore_minimum_quantity = config.get("ignore minimum quantity")
        note = config.get("note", "")

        end_weekday_numbers = []
        for entry in end_weekdays:
            end_weekday_numbers.append(time.strptime(entry, "%A").tm_wday)
        print(end_weekday_numbers)

        if create_orders_till:
            create_orders_till = datetime.datetime.strptime(create_orders_till, '%Y-%m-%d').replace(hour=23, minute=59)
        if create_orders_from:
            create_orders_from = datetime.datetime.strptime(create_orders_from, '%Y-%m-%d')
        else:
            create_orders_from = datetime.datetime.now()

        self.orders_to_create = []
        if auto_close:
            if auto_send:
                if ignore_minimum_quantity:
                    end_action = "auto_close_and_send"
                else:
                    end_action = "auto_close_and_send_min_quantity"
            else:
                end_action = "auto_close"
        else:
            end_action = "no_end_action"

        driver = session.foodsoft_connector.open_driver()
        driver.get(f"{session.foodsoft_connector._url}suppliers/{str(self.supplier_id)}") # get list of existing orders
        date_time = driver.find_element(By.XPATH, "//div[@class='span6'][last()]//tbody/tr/td[2]").text
        last_order_end = get_datetime(date_time)

        end, last_weekday_index = get_next_end(last_end=last_order_end, min_interval=min_interval, end_weekday_numbers=end_weekday_numbers)
        end = end.replace(hour=end_time.tm_hour, minute=end_time.tm_min)
        min_end = datetime.datetime.now() + datetime.timedelta(days=min_order_duration)
        while ((end <= create_orders_till) if create_orders_till else False) or (len(self.orders_to_create) < int(number_of_orders_to_create)):
            print(f"orders created: {len(self.orders_to_create)}")
            print(f"number of orders to create: {int(number_of_orders_to_create)}")
            if end >= create_orders_from and end >= min_end: # TODO: check for duration from now as well?
                if max_order_duration:
                    start = end - datetime.timedelta(days=max_order_duration)
                    start = start.replace(hour=start_time.tm_hour, minute=start_time.tm_min)
                else: # if no max order duration specified, open order at time of creation
                    start = datetime.datetime.now()
                if delivery_duration:
                    pickup = end + datetime.timedelta(days=delivery_duration)
                else:
                    pickup = None
                self.orders_to_create.append(Order(supplier_id=self.supplier_id, start=start, end=end, pickup=pickup, end_action=end_action, note=note))
            end, last_weekday_index = get_next_end(last_end=end, min_interval=min_interval, end_weekday_numbers=end_weekday_numbers, last_weekday_index=last_weekday_index)

        message = compose_order_str(message="Folgende Bestellungen werden angelegt:", orders=self.orders_to_create, locale=session.locale)
        base.write_txt(file_path=base.file_path(path=self.path, folder="display", file_name="Bestellungen"), content=message)

        driver.close()

        self.next_possible_methods = [create_prepared_orders]
        self.completion_percentage = 20
        self.log.append(base.LogEntry(action="orders prepared", done_by=base.full_user_name(session)))

    def create_prepared_orders(self, session, message_subject_suffix="", message_extra_content=""):
        config = base.read_config(self.foodcoop, self.configuration)
        driver = session.foodsoft_connector.open_driver()
        self.created_orders = []

        for order in self.orders_to_create:
            order.create(driver=driver, session=session)
            self.created_orders.append(order)

        if config.get("send message"):
            message_variables = {
                "number of orders": str(len(self.created_orders)),
                "first order start": self.created_orders[0].start_str(session.locale),
                "first order end": self.created_orders[0].end_str(session.locale),
                "first order pickup": self.created_orders[0].pickup_str(session.locale),
                "last order start": self.created_orders[-1].start_str(session.locale),
                "last order end": self.created_orders[-1].end_str(session.locale),
                "last order pickup": self.created_orders[-1].pickup_str(session.locale)
            }

            subject = config.get("message subject", "")
            if subject and message_subject_suffix:
                subject += " "
            subject += message_subject_suffix
            subject = subject.format(**message_variables)
            content = config.get("message content top", "")
            if content:
                content += "\n\n"
            if message_extra_content:
                content += message_extra_content
            bottom_content = config.get("message content bottom", "")
            if bottom_content:
                if message_extra_content:
                    content += "\n\n"
                content += bottom_content
            content = content.format(**message_variables)
            if subject and content:
                driver.get(session.foodsoft_connector._url + "messages/new")
                driver.find_element(By.XPATH, "//input[@id='message_send_method_all']").click()
                driver.find_element(By.ID, "message_subject").send_keys(subject)
                driver.find_element(By.ID, "message_body").send_keys(content)
                driver.find_element(By.XPATH, "//input[@name='commit']").click()

        message = compose_order_str(message="Folgende Bestellungen wurden angelegt:", orders=self.created_orders, locale=session.locale)
        base.write_txt(file_path=base.file_path(path=self.path, folder="display", file_name="Bestellungen"), content=message)

        driver.close()

        self.next_possible_methods = []
        self.completion_percentage = 100
        self.log.append(base.LogEntry(action="orders created", done_by=base.full_user_name(session)))

class Order:
    def __init__(self, supplier_id, start, end=None, pickup=None, end_action="no_end_action", note=""):
        self.supplier_id = supplier_id
        self.start = start
        self.end = end
        self.pickup = pickup
        self.end_action = end_action
        self.note = note
        self.url = None

    def create(self, driver, session):
        driver.get(f"{session.foodsoft_connector._url}orders/new?supplier_id={str(self.supplier_id)}")
        start_date = driver.find_element(By.ID, "order_starts_date_value")
        start_date.clear()
        start_date.send_keys(self.start.strftime('%Y-%m-%d'))
        start_time = driver.find_element(By.ID, "order_starts_time_value")
        start_time.clear()
        start_time.send_keys(self.start.strftime('%H:%M'))
        if self.end:
            driver.find_element(By.ID, "order_ends_date_value").send_keys(self.end.strftime('%Y-%m-%d'))
            driver.find_element(By.ID, "order_ends_time_value").send_keys(self.end.strftime('%H:%M'))
        if self.pickup:
            driver.find_element(By.ID, "order_pickup").send_keys(self.pickup.strftime('%Y-%m-%d'))
        Select(driver.find_element(By.ID, "order_end_action")).select_by_value(self.end_action)
        driver.find_element(By.ID, "order_note").send_keys(self.note)
        driver.find_element(By.XPATH, "//input[@name='commit']").click()
        self.url = driver.current_url

    def start_str(self, locale):
        if self.start <= datetime.datetime.now():
            return "jetzt"
        else:
            return f'{babel.dates.format_skeleton(skeleton="EEEEddMMyy", datetime=self.start, locale=locale)} {babel.dates.format_skeleton(skeleton="Hm", datetime=self.start, locale=locale)}'

    def end_str(self, locale):
        if self.end:
            return f'{babel.dates.format_skeleton(skeleton="EEEEddMMyy", datetime=self.end, locale=locale)} {babel.dates.format_skeleton(skeleton="Hm", datetime=self.end, locale=locale)}'
        else:
            return "(ohne Enddatum)"

    def pickup_str(self, locale):
        if self.pickup:
            return f'{babel.dates.format_skeleton(skeleton="EEEEddMMyy", datetime=self.pickup, locale=locale)}'
        else:
            return "(ohne Abholdatum)"

def get_datetime(s_datetime):
    datetime_patterns = ["%d.%m.%Y %H:%M", "%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M", "%d/%-m/%Y %H:%M", "%Y-%m-%d %H:%M"]

    for pattern in datetime_patterns:
        try:
            return datetime.datetime.strptime(s_datetime, pattern)
        except:
            pass

    print(f"Date is not in expected format: {s_datetime}")

def get_next_end(last_end, min_interval, end_weekday_numbers, last_weekday_index=None):
    if last_weekday_index:
        weekday_index = (last_weekday_index + 1) % len(end_weekday_numbers)
    else:
        weekday_index = 0
    delta = datetime.timedelta((end_weekday_numbers[weekday_index] - min_interval - last_end.weekday()) % 7 + min_interval)
    print(last_end.strftime('%Y-%m-%d'))
    print(delta.days)
    next_end = last_end + datetime.timedelta((end_weekday_numbers[weekday_index] - min_interval - last_end.weekday()) % 7 + min_interval)
    return next_end, weekday_index

def compose_order_str(message, orders, locale):
    for order in orders:
        message += f'\n- {babel.dates.format_datetime(datetime=order.start, format="short", locale=locale)}'
        if order.end:
            message += f' bis {babel.dates.format_datetime(datetime=order.end, format="short", locale=locale)}'
        if order.pickup:
            message += f', abholbereit {babel.dates.format_date(date=order.pickup.date(), format="short", locale=locale)}'
        if order.url:
            message += f" <a href='{order.url}' target='_blank'>Ansehen</a>"
    return message

if __name__ == "__main__":
    importlib.invalidate_caches()
    script = importlib.import_module("script_generic_create_orders") # I don't know why we have to do this, but if the ScriptRun object is just initialized directly (run = ScriptRun(...)), then it doesn't load when we try to load in web ("AttributeError: Can't get attribute 'ScriptRun' on <module '__main__' from 'web.py'>")
    run = script.ScriptRun(foodcoop="krautkoopf", configuration="Supplier X")
    while run.next_possible_methods:
        func = getattr(run, run.next_possible_methods[0].name)
        func()
    run.save()
