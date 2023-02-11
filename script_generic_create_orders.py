"""
Script for creating one or multiple Foodsoft orders for one supplier with fewer clicks, with the option of sending out a Foodsoft message to all members.
"""

import importlib
import datetime
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from webdriver_manager.firefox import GeckoDriverManager

import base
import foodsoft_article
import foodsoft_article_import

# Inputs this script's methods take
create_orders_till = base.Input(name="create_orders_till", required=False, input_format="date")
create_orders_from = base.Input(name="create_orders_from", required=False, input_format="date")
message_subject_suffix = base.Input(name="message_subject_suffix", required=False)
message_extra_content = base.Input(name="message_extra_content", required=False, input_format="textarea")

# Executable script methods
create_orders_directly = base.ScriptMethod(name="create_orders_directly", inputs=[create_orders_till, create_orders_from, message_subject_suffix, message_extra_content])
prepare_orders = base.ScriptMethod(name="prepare_orders", inputs=[create_orders_till, create_orders_from])
create_prepared_orders = base.ScriptMethod(name="create_prepared_orders", inputs=[message_subject_suffix, message_extra_content])

def config_variables(): # List of the special config variables this script uses, whether they are required and how they could look like
    return [
        base.Variable(name="Foodsoft supplier ID", required=True, example=12),
        # base.Variable(name="allow simultaneous orders", required=False, example=False),
        base.Variable(name="time period mode", required=True, example="day"),
        base.Variable(name="time period factor", required=True, example=7),
        # base.Variable(name="day in time period", required=False, example=5),
        # base.Variable(name="weekday filter", required=False, example="sunday"),
        base.Variable(name="order start time", required=False, example="00:00"),
        base.Variable(name="order end time", required=False, example="23:59"),
        base.Variable(name="order duration", required=False, example=6),
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

    def create_orders_directly(self, session, create_orders_till=None, create_orders_from=None, message_subject_suffix="", message_extra_content=""):
        self.prepare_orders(session=session, create_orders_till=create_orders_till, create_orders_from=create_orders_from)
        self.create_prepared_orders(session=session, message_subject_suffix=message_subject_suffix, message_extra_content=message_extra_content)

    def prepare_orders(self, session, create_orders_till=None, create_orders_from=None):
        config = base.read_config(self.foodcoop, self.configuration)
        self.supplier_id = config.get("Foodsoft supplier ID")
        # allow_simultaneous_orders = config.get("allow simultaneous orders")
        time_period_mode = config.get("time period mode")
        time_period_factor = config.get("time period factor")
        # day_in_time_period = config.get("day in time period")
        # weekday_filter = config.get("weekday filter")
        start_time = config.get("order start time", "00:00")
        end_time = config.get("order end time", "23:59")
        order_duration = config.get("order duration")
        delivery_duration = config.get("delivery duration")
        auto_close = config.get("auto close")
        auto_send = config.get("auto send")
        ignore_minimum_quantity = config.get("ignore minimum quantity")
        note = config.get("note", "")

        if create_orders_till:
            create_orders_till = datetime.datetime.strptime(create_orders_till, '%Y-%m-%d').date()
        if create_orders_from:
            create_orders_from = datetime.datetime.strptime(create_orders_from, '%Y-%m-%d').date()
        else:
            create_orders_from = datetime.date.today()
        end_time_parsed = time.strptime(end_time, '%H:%M')

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

        driver = open_driver(session)
        driver.get(f"{session.foodsoft_connector._url}suppliers/{str(self.supplier_id)}") # get list of existing orders
        date_time = driver.find_element(By.XPATH, "(//tbody/tr/td)[2]").text
        last_order_end = get_date(date_time)

        if time_period_mode == "day":
            end_date = last_order_end + datetime.timedelta(days=time_period_factor)
            if not create_orders_till:
                create_orders_till = end_date
            while end_date <= create_orders_till:
                if end_date >= create_orders_from:
                    if order_duration:
                        start_date = end_date - datetime.timedelta(days=order_duration)
                        start_date_str = start_date.strftime('%Y-%m-%d')
                    else: # if order duration is not specified, open order at time of creation
                        start_date_str = datetime.date.today().strftime('%Y-%m-%d')
                        start_time = datetime.datetime.now().strftime('%H:%M')
                    end_date_str = end_date.strftime('%Y-%m-%d')
                    if delivery_duration:
                        pickup_date = end_date + datetime.timedelta(days=delivery_duration)
                        pickup_date_str = pickup_date.strftime('%Y-%m-%d')
                    else:
                        pickup_date_str = ""
                    self.orders_to_create.append(Order(supplier_id=self.supplier_id, start_date=start_date_str, start_time=start_time, end_date=end_date_str, end_time=end_time, pickup_date=pickup_date_str, end_action=end_action, note=note))
                end_date += datetime.timedelta(days=time_period_factor)
        # TODO: add behavior for other time periods (month, year)

        message = "Folgende Bestellungen werden angelegt:"
        for order in self.orders_to_create:
            message += f"\n- {order.start_date} {order.start_time} bis {order.end_date} {order.end_time}"
            if order.pickup_date:
                message += f", abholbereit {order.pickup_date}"
        base.write_txt(file_path=base.file_path(path=self.path, folder="display", file_name="Bestellungen"), content=message)

        self.next_possible_methods = [create_prepared_orders]
        self.completion_percentage = 20
        self.log.append(base.LogEntry(action="orders prepared", done_by=base.full_user_name(session)))

    def create_prepared_orders(self, session, message_subject_suffix="", message_extra_content=""):
        config = base.read_config(self.foodcoop, self.configuration)
        driver = open_driver(session)
        self.created_orders = []

        for order in self.orders_to_create:
            order.create(driver=driver, session=session)
            self.created_orders.append(order)

        if config.get("send message"):
            subject = config.get("message subject", "")
            if subject and message_subject_suffix:
                subject += " "
            subject += message_subject_suffix
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
            if subject and content:
                driver.get(session.foodsoft_connector._url + "messages/new")
                driver.find_element(By.XPATH, "//input[@id='message_send_method_all']").click()
                driver.find_element(By.ID, "message_subject").send_keys(subject)
                driver.find_element(By.ID, "message_body").send_keys(content)
                driver.find_element(By.XPATH, "//input[@name='commit']").click()

        message = "Folgende Bestellungen wurden angelegt:"
        for order in self.created_orders:
            message += f"\n- {order.start_date} {order.start_time} bis {order.end_date} {order.end_time}"
            if order.pickup_date:
                message += f", abholbereit {order.pickup_date}"
            message += f" <a href='{order.url}' target='_blank'>Ansehen</a>"
        base.write_txt(file_path=base.file_path(path=self.path, folder="display", file_name="Bestellungen"), content=message)

        self.next_possible_methods = []
        self.completion_percentage = 100
        self.log.append(base.LogEntry(action="orders created", done_by=base.full_user_name(session)))

class Order:
    def __init__(self, supplier_id, start_date, start_time, end_date="", end_time="", pickup_date="", end_action="no_end_action", note=""):
        self.supplier_id = supplier_id
        self.start_date = start_date
        self.start_time = start_time
        self.end_date = end_date
        self.end_time = end_time
        self.pickup_date = pickup_date
        self.end_action = end_action
        self.note = note
        self.url = None

    def create(self, driver, session):
        driver.get(f"{session.foodsoft_connector._url}orders/new?supplier_id={str(self.supplier_id)}")
        start_date = driver.find_element(By.ID, "order_starts_date_value")
        start_date.clear()
        start_date.send_keys(self.start_date)
        start_time = driver.find_element(By.ID, "order_starts_time_value")
        start_time.clear()
        start_time.send_keys(self.start_time)
        driver.find_element(By.ID, "order_ends_date_value").send_keys(self.end_date)
        driver.find_element(By.ID, "order_ends_time_value").send_keys(self.end_time)
        driver.find_element(By.ID, "order_pickup").send_keys(self.pickup_date)
        Select(driver.find_element(By.ID, "order_end_action")).select_by_value(self.end_action)
        driver.find_element(By.ID, "order_note").send_keys(self.note)
        driver.find_element(By.XPATH, "//input[@name='commit']").click()
        self.url = driver.current_url

def open_driver(session):
    driver = webdriver.Firefox(executable_path=GeckoDriverManager().install())
    driver.get(session.foodsoft_connector._url)
    for cookie in session.foodsoft_connector._session.cookies:
        driver.add_cookie({
            'name': cookie.name,
            'value': cookie.value,
            'path': cookie.path,
            'expiry': cookie.expires,
        })
    return driver

def get_date(s_date):
    date_patterns = ["%d.%m.%Y %H:%M", "%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M", "%d/%-m/%Y %H:%M", "%Y-%m-%d %H:%M"]

    for pattern in date_patterns:
        try:
            return datetime.datetime.strptime(s_date, pattern).date()
        except:
            pass

    print(f"Date is not in expected format: {s_date}")

if __name__ == "__main__":
    importlib.invalidate_caches()
    script = importlib.import_module("script_generic_create_orders") # I don't know why we have to do this, but if the ScriptRun object is just initialized directly (run = ScriptRun(...)), then it doesn't load when we try to load in web ("AttributeError: Can't get attribute 'ScriptRun' on <module '__main__' from 'web.py'>")
    run = script.ScriptRun(foodcoop="krautkoopf", configuration="Supplier X")
    while run.next_possible_methods:
        func = getattr(run, run.next_possible_methods[0].name)
        func()
    run.save()
