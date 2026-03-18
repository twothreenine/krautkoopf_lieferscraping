"""
Script for creating an ordergroup with up to 3 associated users (Foodsoft + Discourse), based on data submitted by a form in the following layout:

$# bestellgruppe-groesse: 3
$# mitgliedsbeitrag: 10
$# bestellgruppe: Testgruppe XY
$# eintrittsdatum: 2025-08-28
$#

Person 1:
$# nickname1: abcdefg
$# vorname1: Abc
$# nachname1: Defg
$# pronomen1: xyz
$# email1: foo11@bar.net
$# telefon1: +0123 456789
$# mein-nutzen1: bla blub
$# einkistln1: Ja, ich kann beim Einkistln mitmachen.
$# arbeitsgruppen1: Finanzteam (Abrechnungen), Plenumskoordination
$# wohnort1: Testort
$# sonstiges1: Dies ist ein Text.

Mit Zeilenumbrüchen.
$# profilbild1: Zwischenablage_08-21-2025_01.png
$#

Person 2:
$# nickname2: abcdefg2
$# vorname2: abc2
$# nachname2: defg2
$# pronomen2: xyz2
$# email2: foo12bar@net.de
$# telefon2: 0123456
$# mein-nutzen2:
$# einkistln2:
$# arbeitsgruppen2:
$# wohnort2:
$# sonstiges2:
$# profilbild2: foto2.jpg
$#

Person 3:
$# nickname3: abcdefg3
$# vorname3: abc3
$# nachname3: defg3
$# pronomen3: xyz3
$# email3: foo13@bar.net
$# telefon3: 0223459
$# mein-nutzen3:
$# einkistln3: Ja, ich kann beim Einkistln mitmachen.
$# arbeitsgruppen3:
$# wohnort3:
$# sonstiges3:
$# profilbild3: foto3.jpg
$#











$# bestellgruppe-groesse: 2
$# mitgliedsbeitrag: 10
$# bestellgruppe: Testgruppe XY
$# eintrittsdatum: 2025-08-28
$#

Person 1:
$# nickname1: abcdefg
$# vorname1: Abc
$# nachname1: Defg
$# pronomen1: xyz
$# email1: foo11@bar.net
$# telefon1: +0123 456789
$# mein-nutzen1: bla blub
$# einkistln1: Ja, ich kann beim Einkistln mitmachen.
$# arbeitsgruppen1: Finanzteam (Abrechnungen), Plenumskoordination
$# wohnort1:
$# sonstiges1: Dies ist ein Text.

Mit Zeilenumbrüchen.
$# profilbild1: Zwischenablage_08-21-2025_01.png
$#

Person 2:
$# nickname2:
$# vorname2:
$# nachname2: 
$# pronomen2: 
$# email2: 
$# telefon2: 
$# mein-nutzen2:
$# einkistln2:
$# arbeitsgruppen2:
$# wohnort2:
$# sonstiges2:
$# profilbild2: 
$#

Person 3:
$# nickname3: 
$# vorname3: 
$# nachname3: 
$# pronomen3: 
$# email3: 
$# telefon3: 
$# mein-nutzen3:
$# einkistln3: 
$# arbeitsgruppen3:
$# wohnort3:
$# sonstiges3:
$# profilbild3: 
$#
"""

import datetime
import secrets
import re
import time
import babel.dates
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager
from pydiscourse import DiscourseClient
import ethercalc

import base

# Inputs this script's methods take
form_data = base.Input(name="form_data", required=True, input_format="textarea")
profile_images = base.Input(name="profile_images", required=False, input_format="files")
membership_fee = base.Input(name="membership_fee", required=True, input_format="number", other_attributes=["step=0.01"])
ordergroup_name = base.Input(name="ordergroup_name", required=False, input_format="text")
nick = base.Input(name="nick", required=False, input_format="text")
email = base.Input(name="email", required=False, input_format="email")
first_name = base.Input(name="first_name", required=True, input_format="text")

# Executable script methods
first_try = base.ScriptMethod(name="first_try", inputs=[form_data, profile_images])
retry_membership_fee = base.ScriptMethod(name="retry_membership_fee", inputs=[membership_fee])
confirm_no_engagement = base.ScriptMethod(name="confirm_no_engagement")
retry_ordergroup_name = base.ScriptMethod(name="retry_ordergroup_name", inputs=[ordergroup_name])
retry_nick = base.ScriptMethod(name="retry_nick", inputs=[nick])
retry_email = base.ScriptMethod(name="retry_email", inputs=[email])
retry_first_name = base.ScriptMethod(name="retry_first_name", inputs=[first_name])
retry_unknown_field = base.ScriptMethod(name="retry_unknown_field")

def config_variables(): # List of the special config variables this script uses, whether they are required and how they could look like
    return [
        # base.Variable(name="temporary email address", required=True, example="info@my-foodcoop.org", description="must not be an email of a Foodsoft user"),
        base.Variable(name="Discourse URL", required=True, example="discourse.my-foodcoop.org/"),
        base.Variable(name="Discourse API username", required=True, example="My_API_User"),
        base.Variable(name="Discourse API key", required=True, example="some-long-string"),
        base.Variable(name="Discourse SSO secret", required=True, example="some-weird-string"),
        base.Variable(name="EtherCalc host", required=True, example="https://ethercalc.my-foodcoop.org"),
        base.Variable(name="Einkistln Ethercalc", required=True, example="einkistln-page"),
        base.Variable(name="Putzdienst Ethercalc", required=True, example="putzdienst-page"),
        base.Variable(name="welcome mail subject", required=True, example="Willkommen bei unserer FoodCoop, \{user_nick\}!"),
        base.Variable(name="welcome mail body", required=True, example="some-long-string with \{user_nick\}, \{user_email\}, \{temporary_password\}")
        ]

def excel_date(date1):
    delta = date1 - datetime.date(1899, 12, 30)
    return int(delta.days)

class FormData:
    def __init__(self, form_data):
        self.form_data = form_data
    
    def get_form_value(self, key):
        return self.form_data.split("$# " + key + ":")[1].split("\n$#")[0].strip()
    
    def parse_user_data(self, number):
        number = str(number)
        if self.get_form_value("nickname" + number) != "":
            return User(self, number)
        else:
            return None

class User:
    def __init__(self, form_data, number):
        self.nick = form_data.get_form_value("nickname" + number)
        self.first_name = form_data.get_form_value("vorname" + number)
        self.last_name = form_data.get_form_value("nachname" + number)
        self.pronouns = form_data.get_form_value("pronomen" + number)
        self.email = form_data.get_form_value("email" + number)
        self.phone = form_data.get_form_value("telefon" + number)
        self.my_benefit = form_data.get_form_value("mein-nutzen" + number)
        if form_data.get_form_value("einkistln" + number):
            self.einkistln = True
        else:
            self.einkistln = False
        self.workgroups = form_data.get_form_value("arbeitsgruppen" + number)
        self.place_of_residence = form_data.get_form_value("wohnort" + number)
        self.misc = form_data.get_form_value("sonstiges" + number)
        self.picture = form_data.get_form_value("profilbild" + number)
        self.temporary_password = secrets.token_urlsafe(20)
        self.valid_nick = False
        self.valid_email = False
        self.valid_first_name = False
        self.foodsoft_id = None

class ScriptRun(base.Run):
    def __init__(self, foodcoop, configuration):
        super().__init__(foodcoop=foodcoop, configuration=configuration)
        self.next_possible_methods = [first_try]

    def first_try(self, session, form_data, profile_images=None):
        form_data = FormData(form_data)
        self.config = base.read_config(self.foodcoop, self.configuration)
        self.discourse_url = self.config.get("Discourse URL")

        if profile_images:
            for file in profile_images:
                file.save(base.file_path(path=self.path, folder="img", file_name=file.filename))

        # parse form data
        self.ordergroup_size = int(form_data.get_form_value("bestellgruppe-groesse"))
        self.membership_fee = float(form_data.get_form_value("mitgliedsbeitrag").replace(",", "."))
        self.ordergroup_name = form_data.get_form_value("bestellgruppe")
        self.entry_date = datetime.datetime.strptime(form_data.get_form_value("eintrittsdatum"), '%Y-%m-%d').date()
        self.users = []
        for i in [1, 2, 3]:
            user = form_data.parse_user_data(i)
            if user:
                self.users.append(user)
        
        message = f"Bestellgruppe '{self.ordergroup_name}' mit folgenden Benutzer*innen soll erstellt werden: (laut Anmeldeformular)"
        for user in self.users:
            message += f"\n- {user.nick} ({user.first_name} {user.last_name})"
        base.write_txt(file_path=base.file_path(path=self.path, folder="display", file_name="Bestellgruppe"), content=message)
        
        self.allow_without_engagement = False
        self.validate_data(session)
        
    def validate_data(self, session):
        if self.membership_fee < self.ordergroup_size + 1: # minimum membership fee
            message = f"{str(self.membership_fee)} € ist ein zu geringer Mitgliedsbeitrag für eine Bestellgruppe mit {str(self.ordergroup_size)} Mitglied(ern)."
            self.ask_for_valid_data(session, retry_membership_fee, message)
        else:
            for user in self.users:
                if not (re.fullmatch(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b', user.email)):
                    message = f"E-Mail-Adresse '{user.email}' ist ungültig."
                    self.ask_for_valid_data(session, retry_email, message, user)
                    break
            engagement = False
            for user in self.users:
                if user.einkistln:
                    engagement = True
                if user.workgroups:
                    engagement = True
            if not engagement and not self.allow_without_engagement:
                message = f"Kein Mitglied der Bestellgruppe hat sich zum Einkistln oder für eine Arbeitsgruppe bereiterklärt."
                base.write_txt(file_path=base.file_path(path=self.path, folder="display", file_name="Hinweise"), content=message)
                self.next_possible_methods = [confirm_no_engagement]
                self.completion_percentage = 20
                if not self.log:
                    self.log.append(base.LogEntry(action="first try done", done_by=base.full_user_name(session)))
            else:
                # continue if data is valid
                self.create_Foodsoft_objects(session)

        '''
        if self.ordergroup_name in self.taken_ordergroup_names:
            message = f"'{self.ordergroup_name}' ist als Bestellgruppen-Name bereits vergeben.\n\nVergebene Namen:"
            for ordergroup_name in self.taken_ordergroup_names:
                message += f"\n- {ordergroup_name}"
            self.ask_for_valid_data(session, retry_ordergroup_name, message)
        
        if len(self.ordergroup_name) > 25:
            message = f"'{self.ordergroup_name}' ({str(len(self.ordergroup_name))} Zeichen) ist zu lang: Bestellgruppen-Name darf max. 25 Zeichen lang sein."
            self.ask_for_valid_data(session, retry_ordergroup_name, message)

        for user in self.users:
            if user.nick in self.taken_nicks:
                message = f"Nickname '{user.nick}' (für {user.first_name} {user.last_name}) ist bereits vergeben.\n\nVergebene Nicknamen:"
                for nick in self.taken_nicks:
                    message += f"\n- {nick}"
                self.ask_for_valid_data(session, retry_nick, message, user)
            elif user.nick in [u.nick for u in self.users if u != user]:
                message = f"Nickname '{user.nick}' kommt in den eingegebenen Daten mehrfach vor."
                self.ask_for_valid_data(session, retry_nick, message, user)
            elif len(user.nick) > 25:
                message = f"'{user.nick}' ({str(len(user.nick))} Zeichen) ist zu lang: Nickname darf max. 25 Zeichen lang sein."
                self.ask_for_valid_data(session, retry_nick, message, user)
            else:
                user.valid_nick = True

            if user.email in self.taken_email_addresses:
                message = f"E-Mail-Adresse '{user.email}' ist bereits vergeben."
                self.ask_for_valid_data(session, retry_email, message, user)
            elif user.email in [u.email for u in self.users if u != user]:
                message = f"E-Mail-Adresse '{user.email}' kommt in den eingegebenen Daten mehrfach vor."
                self.ask_for_valid_data(session, retry_email, message, user)
            else:
                user.valid_email = True
            
            if len(user.first_name) > 50:
                message = f"'{user.nick}' ({str(len(user.nick))} Zeichen) ist zu lang: Vorname darf max. 50 Zeichen lang sein."
                self.ask_for_valid_data(session, retry_first_name, message, user)
            else:
                user.valid_first_name = True
        '''
    
    def ask_for_valid_data(self, session, method, message, user=None):
        self.overwrite_data_of = user
        base.write_txt(file_path=base.file_path(path=self.path, folder="display", file_name="Hinweise"), content=message)
        self.next_possible_methods = [method]
        self.completion_percentage = 20
        if not self.log:
            self.log.append(base.LogEntry(action="first try done", done_by=base.full_user_name(session)))

    def retry_membership_fee(self, session, membership_fee):
        self.membership_fee = float(membership_fee)
        self.validate_data(session)

    def retry_ordergroup_name(self, session, ordergroup_name=""):
        if ordergroup_name:
            self.ordergroup_name = ordergroup_name
        self.create_Foodsoft_objects(session)

    def retry_nick(self, session, nick=""):
        if nick:
            self.overwrite_data_of.nick = nick
        self.create_Foodsoft_objects(session)

    def retry_email(self, session, email=""):
        if email:
            self.overwrite_data_of.email = email
        self.validate_data(session)

    def retry_first_name(self, session, first_name):
        self.overwrite_data_of.first_name = first_name
        self.create_Foodsoft_objects(session)

    def retry_unknown_field(self, session):
        pass

    def confirm_no_engagement(self, session):
        self.allow_without_engagement = True
        self.validate_data(session)
        
    def create_Foodsoft_objects(self, session):
        driver = session.foodsoft_connector.open_driver()
        error = None

        for user in [u for u in self.users if not u.foodsoft_id]:
            driver.get(f"{session.foodsoft_connector._url}admin/users/new")
            driver.find_element(By.ID, "user_first_name").send_keys(user.first_name)
            driver.find_element(By.ID, "user_last_name").send_keys(user.last_name)
            driver.find_element(By.ID, "user_email").send_keys(user.email)
            driver.find_element(By.ID, "user_nick").send_keys(user.nick)
            driver.find_element(By.ID, "user_password").send_keys(user.temporary_password)
            driver.find_element(By.ID, "user_password_confirmation").send_keys(user.temporary_password)
            driver.find_element(By.ID, "user_phone").send_keys(user.phone)
            Select(driver.find_element(By.ID, "user_settings_attributes_profile_language")).select_by_value("de")
            driver.find_element(By.XPATH, "//input[@id='user_settings_attributes_profile_phone_is_public']").click()
            driver.find_element(By.XPATH, "//input[@id='user_settings_attributes_profile_email_is_public']").click()
            driver.find_element(By.XPATH, "//input[@id='user_settings_attributes_profile_name_is_public']").click()
            driver.find_element(By.XPATH, "//input[@id='user_settings_attributes_notify_negative_balance']").click()

            driver.find_element(By.XPATH, "//input[@type='submit']").click()
            try:
                error = driver.find_element(By.XPATH, "//span[@class='help-inline']")
            except NoSuchElementException:
                user.foodsoft_id = int(driver.current_url.split("/")[-1])
            if error:
                invalid_field = driver.find_element(By.XPATH, "//span[@class='help-inline']//preceding-sibling::input[1]")
                invalid_value = invalid_field.get_attribute('value')
                message = f"'{invalid_value}' ({str(len(str(invalid_value)))} Zeichen) {error.text}"
                match invalid_field.get_attribute('id'):
                    case "user_first_name":
                        method = retry_first_name
                    case "user_nick":
                        method = retry_nick
                    case "user_email":
                        method = retry_email
                    case _:
                        method = retry_unknown_field
                        message += f"\nNicht vorgesehenes Feld für Validierung: {invalid_field.get_attribute('id')}"
                driver.close()
                self.ask_for_valid_data(session, method, message, user)
                break
            else:
                # driver.get(f"{session.foodsoft_connector._url}admin/users/{user.foodsoft_id}/edit")
                # driver.find_element(By.ID, "user_email").clear()
                # driver.find_element(By.ID, "user_email").send_keys(self.config.get("temporary email address"))
                # driver.find_element(By.XPATH, "//input[@type='submit']").click()

                self.create_Discourse_account(user)

                # driver.get(f"{session.foodsoft_connector._url}admin/users/{user.foodsoft_id}/edit")
                # driver.find_element(By.ID, "user_email").clear()
                # driver.find_element(By.ID, "user_email").send_keys(user.email)
                # driver.find_element(By.XPATH, "//input[@type='submit']").click()
        
        if not error:
            driver.get(f"{session.foodsoft_connector._url}admin/ordergroups/new")
            driver.find_element(By.ID, "ordergroup_name").send_keys(self.ordergroup_name)
            driver.find_element(By.ID, "ordergroup_contact_person").send_keys(self.users[0].nick)
            driver.find_element(By.ID, "ordergroup_contact_phone").send_keys(self.users[0].phone)
            driver.find_element(By.ID, "ordergroup_contact_address").send_keys(self.users[0].place_of_residence)
            driver.find_element(By.ID, "ordergroup_custom_fields_membership_fee").send_keys(str(self.membership_fee * (-1)))
            ordergroup_user_tokens_element = driver.find_element(By.ID, "ordergroup_user_tokens")
            driver.execute_script("arguments[0].style.display='block';", ordergroup_user_tokens_element)
            ordergroup_user_tokens_element.send_keys(",".join([str(user.foodsoft_id) for user in self.users]))

            driver.find_element(By.XPATH, "//input[@type='submit']").click()
            try:
                error = driver.find_element(By.XPATH, "//span[@class='help-inline']")
            except NoSuchElementException:
                self.ordergroup_id = int(driver.current_url.split("/")[-1])
                self.compose_welcome_emails(session, driver)
            if error:
                invalid_field = driver.find_element(By.XPATH, "//span[@class='help-inline']//preceding-sibling::input[1]")
                invalid_value = invalid_field.get_attribute('value')
                message = f"'{invalid_value}' ({str(len(str(invalid_value)))} Zeichen) {error.text}"
                match invalid_field.get_attribute('id'):
                    case "ordergroup_name":
                        method = retry_ordergroup_name
                    case _:
                        method = retry_unknown_field
                        message += f"\nNicht vorgesehenes Feld für Validierung: {invalid_field.get_attribute('id')}"
                driver.close()
                self.ask_for_valid_data(session, method, message)
    
    def create_Discourse_account(self, user):
        client = DiscourseClient(
            self.config.get("Discourse URL"), 
            api_username=self.config.get("Discourse API username"), 
            api_key=self.config.get("Discourse API key"))
        
        if user.picture:
            avatar = client.upload_image(image=base.file_path(path=self.path, folder="img", file_name=user.picture), upload_type="avatar", synchronous=True)
            discourse_user = client.sync_sso(
                sso_secret = self.config.get("Discourse SSO secret"),
                username = user.nick,
                name = f"{user.first_name} {user.last_name}",
                email = user.email,
                external_id = f"krautkoopf/{str(user.foodsoft_id)}",
                avatar_url=avatar.get("url"),
                avatar_force_update=True
            )
        else:
            discourse_user = client.sync_sso(
                sso_secret = self.config.get("Discourse SSO secret"),
                username = user.nick,
                name = f"{user.first_name} {user.last_name}",
                email = user.email,
                external_id = f"krautkoopf/{str(user.foodsoft_id)}"
            )

        user.discourse_id = discourse_user.get("id")
        user.discourse_username = discourse_user.get("username")

        client.update_user(
            username = user.discourse_username,
            location = user.place_of_residence,
            user_fields = {
                '10': user.pronouns,
                '8': user.phone,
                '7': self.entry_date.strftime("%d.%m.%Y"),
                '9': self.ordergroup_name,
                '1': user.my_benefit,
                '3': user.workgroups,
                '6': self.entry_date.strftime("%d.%m.%Y")
            })
        
        # Add new user to "all" group
        group = client.group("all")
        group_id = group.get("group").get("id")
        client.add_group_member(group_id, user.discourse_username)

    """ create_Discourse_account_old_way 
    def create_Discourse_account_old_way(self, session, driver, user):
        # deprecated
        user_driver = session.foodsoft_connector.open_driver()
        user_driver.get(f"{session.foodsoft_connector._url}admin/users/{user.foodsoft_id}")
        user_driver.find_element(By.XPATH, "//a[@data-method='post']").click()
        Alert(user_driver).accept()
        time.sleep(1)
        user_driver.get(f"{session.foodsoft_connector._url}links/15") # open Discourse
        if self.logout_discourse(user_driver): # session user might be logged in in Discourse, so we have to logout and re-login
            user_driver.get(f"{session.foodsoft_connector._url}links/15")
        time.sleep(10)
        admin_driver = driver
        admin_driver.get(f"{session.foodsoft_connector._url}links/2") # open Webmail
        time.sleep(2)
        email = admin_driver.find_element(By.XPATH, "//table[@id='messagelist']/tbody/tr[1]/td[@class='subject']/span[@class='subject']/a")
        ActionChains(driver).double_click(email).perform()
        time.sleep(1)
        link_element = admin_driver.find_element(By.XPATH, "//div[@id='messagebody']/descendant::a") # //div[@id='messagebody']//a
        link = link_element.get_attribute('href')
        if link.startswith(f"{self.discourse_url}u/activate-account/"):
            user_driver.get(link)
            time.sleep(2)
            user_driver.find_element(By.XPATH, "//button[@class='btn btn-text activate-account-button btn-primary']").click()
            time.sleep(2)
            self.logout_discourse(user_driver)

            client = DiscourseClient(
                self.config.get("Discourse URL"), 
                api_username=self.config.get("Discourse API username"), 
                api_key=self.config.get("Discourse API key"))
            discourse_user = client.user_by_external_id(f"krautkoopf%2F{user.foodsoft_id}")
            user.discourse_username = discourse_user.get("username")
            if self.ordergroup_size > 1:
                ordergroup_size_string = f"{str(self.ordergroup_size)} Personen"
            else:
                ordergroup_size_string = "1 Person"
            client.update_user(username=user.discourse_username,
                               location=user.place_of_residence,
                               user_fields={
                                    '10': user.pronouns,
                                    '8': user.phone,
                                    '7': self.entry_date.strftime("%d.%m.%Y"),
                                    '9': f"{self.ordergroup_name} ({ordergroup_size_string})",
                                    '1': user.my_benefit,
                                    '3': user.workgroups,
                                    '6': datetime.date.today().strftime("%d.%m.%Y")
                                })
            # with open(base.file_path(path=self.path, folder="img", file_name=user.picture), "rb") as f:
            #     image = f.read()
            response = client.upload_image(image=base.file_path(path=self.path, folder="img", file_name=user.picture), upload_type="avatar", user_id=int(discourse_user.get("id")), synchronous=True)
            print(response)
            time.sleep(2)
            # admin_driver.get(f"{self.discourse_url}/admin/users/{discourse_user.get("id")}/{user.discourse_username}")
            # time.sleep(1)
            # admin_driver.find_element(By.XPATH, "//button[@title='SSO-Payload anzeigen']").click()
            # time.sleep(1)
            # last_payload = admin_driver.find_element(By.XPATH, "//div[@text()='Letzter Payload']//following-sibling::div").text
            # print(last_payload)
            # client.sync_sso(
            #     sso_secret=self.config.get("Discourse SSO secret"),
            #     username=user.nick.replace(" ", "+"),
            #     name=f"{user.first_name.replace(" ", "+")}+{user.last_name.replace(" ", "+")}+",
            #     email=f"{user.email.replace("@", "%40")}",
            #     external_id=f"krautkoopf%2F{user.foodsoft_id}"
            # )
            
            client.update_email(username=user.discourse_username, email=user.email) # confirmation email will be sent to new email address
        else:
            print("Faulty email!")
        """

    def compose_welcome_emails(self, session, driver):
        for user in self.users:
            welcome_email = f"An: {user.first_name} {user.last_name} <{user.email}>"
            welcome_email += f"\nBetreff: {self.config.get("welcome mail subject").format(user_nick=user.nick)}"
            welcome_email += f"\nText:\n{self.config.get("welcome mail body").format(user_nick=user.nick, temporary_password=user.temporary_password, user_email=user.email)}"
            base.write_txt(file_path=base.file_path(path=self.path, folder="display", file_name=f"Willkommensmail an {user.nick}"), content=welcome_email)

        # didn't work, gave up for now:
        # driver.get(f"{session.foodsoft_connector._url}links/2") # open Webmail
        # for user in self.users:
        #     time.sleep(1)
        #     driver.get(".../?_task=mail&_action=compose")
        #     time.sleep(1)
        #     recipient = driver.find_element(By.XPATH, "//ul[@class='form-control recipient-input ac-input rounded-left ui-sortable']/li/input")
        #     recipient.click()
        #     recipient.send_keys(f"{user.first_name} {user.last_name} <{user.email}>")
        #     driver.find_element(By.XPATH, "//div[@id='compose_subject']/div").send_keys(self.config.get("welcome mail subject").format(user_nick=user.nick))
        #     compose_iframe = driver.find_element(By.XPATH, "//iframe[@id='composebody_ifr']")
        #     driver.switch_to.frame(compose_iframe)
        #     assert "We Leave From Here" in driver.page_source # what does this do?
        #     driver.find_element(By.ID("tinymce")).send_keys(self.config.get("welcome mail body").format(user_nick=user.nick, temporary_password=user.temporary_password, user_email=user.email))
        #     time.sleep(1)
        #     driver.switch_to.default_content()
        #     driver.find_element(By.XPATH, "//a[@class='save draft']").click()
        #     time.sleep(2)
        
        driver.close()
        self.add_to_ethercalcs(session)
    
    def add_to_ethercalcs(self, session):
        ecalc = ethercalc.EtherCalc(self.config.get("EtherCalc host"))
        self.einkistln_users = [u for u in self.users if u.einkistln]
        for user in self.einkistln_users:
            raw_participants = ecalc.export(page=self.config.get("Einkistln Ethercalc") + ".2", format="python")
            einkistln_participants = []
            for row in raw_participants:
                if raw_participants.index(row) == 0 or row[0]:
                    einkistln_participants.append(row)
            new_row = str(len(einkistln_participants) + 1)

            ecalc.command(page=self.config.get("Einkistln Ethercalc") + ".2", command=[
                f"set A{new_row} text t {user.nick}",
                f"set B{new_row} constant nl 0 FALSE",
                f"set C{new_row} constant nl 1 TRUE",
                f"set E{new_row} constant nd {excel_date(self.entry_date)} {self.entry_date.strftime("%Y-%m-%d")}",
                f"set H{new_row} value n {user.foodsoft_id}",
                f"set I{new_row} text t {user.discourse_username}"
            ])
        
        for user in self.users:
            raw_participants = ecalc.export(page=self.config.get("Putzdienst Ethercalc") + ".2", format="python")
            putzdienst_participants = []
            for row in raw_participants:
                if raw_participants.index(row) == 0 or row[0]:
                    putzdienst_participants.append(row)
            new_row = str(len(putzdienst_participants) + 1)

            ecalc.command(page=self.config.get("Putzdienst Ethercalc") + ".2", command=[
                f"set A{new_row} text t {user.nick}",
                f"set B{new_row} constant nl 0 FALSE",
                f"set C{new_row} constant nl 1 TRUE",
                f"set E{new_row} constant nd {excel_date(self.entry_date)} {self.entry_date.strftime("%Y-%m-%d")}",
                f"set H{new_row} value n {user.foodsoft_id}",
                f"set I{new_row} text t {user.discourse_username}"
            ])

        self.finish(session)
    
    def finish(self, session):
        result = f"- Foodsoft-Bestellgruppe <a href='{session.foodsoft_connector._url}admin/ordergroups/{self.ordergroup_id}' target='_blank'>{self.ordergroup_name}</a> mit {str(self.membership_fee)} € Mitgliedsbeitrag erstellt."
        foodsoft_user_strings = []
        discourse_user_strings = []
        for user in self.users:
            foodsoft_user_strings.append(f"<a href='{session.foodsoft_connector._url}admin/users/{user.foodsoft_id}' target='_blank'>{user.nick}</a> ({user.first_name} {user.last_name})")
            discourse_user_strings.append(f"<a href='{self.config.get("Discourse URL")}u/{user.discourse_username}/summary' target='_blank'>{user.discourse_username}</a>")
        result += f"\n- Foodsoft-User erstellt: {', '.join(foodsoft_user_strings)}"
        result += f"\n- Discourse-User erstellt: {', '.join(discourse_user_strings)}"
        result += f"\n- Willkommensmail(s) entworfen - bitte von <a href='{session.foodsoft_connector._url}links/2' target='_blank'>Info-Postfach</a> ausschicken."
        if self.einkistln_users:
            result += f"\n- {', '.join([user.nick for user in self.einkistln_users])} in Einkistln-Tabelle eintragen."
        else:
            result += f"\n- Niemand in Einkistln-Tabelle eingetragen."
        result += f"\n- {', '.join([user.nick for user in self.users])} in Putzdienst-Tabelle eintragen."
        result += "\n\nSonstige Angaben:"
        for user in self.users:
            result += f'\n- {user.nick}: "{user.misc}"'
        result += "\n\nTo Dos:\n- Willkommensmail abschicken\n- Ausmachen, wer Buddy ist"
        
        base.write_txt(file_path=base.file_path(path=self.path, folder="display", file_name="Ergebnis"), content=result)

        self.next_possible_methods = []
        self.completion_percentage = 90
        self.log.append(base.LogEntry(action="Accounts created", done_by=base.full_user_name(session)))
    
    def logout_discourse(self, driver):
        # deprecated
        logged_in = True
        try:
            driver.find_element(By.XPATH, "//button[@id='toggle-current-user']").click()
        except NoSuchElementException:
            logged_in = False
            return False
        if logged_in:
            driver.find_element(By.ID, "user-menu-button-profile").click()
            driver.find_element(By.XPATH, "//li[@class='logout']/button").click()
            return True
