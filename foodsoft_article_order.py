import csv
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

def get_orders_from_csv(session, driver, supplier_id):
    driver.get(f"{session.foodsoft_connector._url}suppliers/{str(supplier_id)}") # get list of existing orders
    for el in driver.find_elements(By.XPATH, "//div[@class='span6'][last()]//tbody/tr"): # get csv of last closed order
        try:
            order_balancing_a = el.find_element(By.XPATH, "//td[3]/a")
        except NoSuchElementException:
            continue # open orders don't have a link to the balancing menu, so we skip those
        order_id = order_balancing_a.get_attribute("href").split("=")[-1]
        return order_id, list(csv.reader(session.foodsoft_connector._get(f"{get_order_url(session, order_id)}.csv", session.foodsoft_connector._default_header).content.decode('iso8859-15').splitlines(), delimiter=';')) # not the correct decoding, but works

def get_order_url(session, order_id):
    return f"{session.foodsoft_connector._url}orders/{order_id}"

def compose_order_message(session, order_id, articles_put_in_cart=None, articles_to_order_manually="", order_manually_prefix="", failed_articles=None, notifications=None, prefix=""):
    locales = session.locales
    text = ""
    if prefix:
        text += f"{prefix}\n\n"
    text += f'{locales["foodsoft_article_order"]["order processed"].format(order_url=get_order_url(session, order_id))}\n'
    if articles_put_in_cart:
        text += f'\n{locales["foodsoft_article_order"]["articles put in cart"]}:'
        for ac in articles_put_in_cart:
            text += f"\n- {ac}"
        text += "\n"
    if articles_to_order_manually:
        text += f'\n{locales["foodsoft_article_order"]["articles to order manually"]}:'
        if order_manually_prefix:
            text += f'\n{order_manually_prefix}'
        for am in articles_to_order_manually:
            text += f"\n- {am}"
        text += "\n"
    if failed_articles:
        text += f'\n{locales["foodsoft_article_order"]["failed articles"]}:'
        for fa in failed_articles:
            text += f"\n- {fa}"
        text += "\n"
    if notifications:
        text += f'\n{locales["foodsoft_article_order"]["notifications"]}:'
        for notification in notifications:
            text += f'\n- {notification}'
        text += "\n"
    return text
