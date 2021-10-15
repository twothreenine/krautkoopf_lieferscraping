import bottle
import re
import base

foodcoop_name, foodsoft_url, foodsoft_user, foodsoft_password = base.read_foodsoft_config()
logged_in = False
messages = []

def style():
    style = 'width: 200px; font-family: Calibri, Verdana, sans-serif;'
    return style

def read_messages():
    content = ""
    global messages
    if messages:
        content += messages[0]
    if len(messages) > 1:
        for message in messages[1:]:
            content += "<br/>" + message
    messages = []
    return content

def supplier_link(supplier):
    return bottle.template("<a href='/{{foodcoop}}/{{supplier}}'>{{supplier}}</a>", foodcoop=foodcoop_name, supplier=supplier)

def output_download_button(supplier, output):
    source = "/download/" + supplier + "/" + output
    # source = "/download/Notizen.txt"
    return "<a href='{}' class='button' download>⤓</a> ".format(source)

def main_page():
    content = ""
    config = base.read_config()
    suppliers = [x for x in config]
    if suppliers:
        content += supplier_link(suppliers[0])
        if "note" in suppliers[0]:
            content += " (" + suppliers[0]["note"] + ")"
    if len(suppliers) > 1:
        for supplier in suppliers[1:]:
            content += "<br/>" + supplier_link(supplier)
            if "note" in supplier:
                content += " (" + supplier["note"] + ")"

    return bottle.template('templates/main.tpl', messages=read_messages(), foodcoop=foodcoop_name, foodcoop_name=foodcoop_name.capitalize(), suppliers=content)

def login_page(foodcoop):
    if foodcoop == foodcoop_name:
        return bottle.template('templates/login.tpl', messages=read_messages(), foodcoop=foodcoop_name, foodcoop_name=foodcoop_name.capitalize(), foodsoft_user=foodsoft_user)
    else:
        return bottle.template('templates/false_url.tpl', foodcoop=foodcoop)

def supplier_page(supplier):
    output_content = ""
    outputs = base.get_outputs(foodcoop_name=foodcoop_name, supplier=supplier)
    outputs.reverse()
    for index in range(5):
        if index+1 > len(outputs):
            break
        if output_content:
            output_content += "<br/>"
        output_content += output_download_button(supplier=supplier, output=outputs[index]) + str(outputs[index])
    config_content = ""
    config = base.read_config(supplier=supplier)
    for detail in config:
        if config_content:
            config_content += "<br/>"
        config_content += str(detail) + ": "
        if str(detail) == "manual changes":
            config_content += str(len(config[detail])) + " manual changes"
        else:
            config_content += str(config[detail])
    return bottle.template('templates/supplier.tpl', foodcoop=foodcoop_name, foodcoop_name=foodcoop_name.capitalize(), supplier=supplier, output_content=output_content, config_content=config_content)

@bottle.route('/<foodcoop>')
def login(foodcoop):
    global logged_in
    if logged_in:
        return main_page()
    else:
        return login_page(foodcoop)

@bottle.route('/<foodcoop>', method='POST')
def do_main(foodcoop):
    submitted_form = bottle.request.forms
    for thing in submitted_form:
        print(thing)
    global logged_in
    if 'password' in submitted_form:
        password = submitted_form.get('password')
        if password == foodsoft_password:
            logged_in = True
            messages.append("Login erfolgreich.")
            return main_page()
        else:
            messages.append("Login fehlgeschlagen.")
            return login_page(foodcoop)
    elif 'logout' in submitted_form:
        logged_in = False
        messages.append("Logout erfolgreich.")
        return login_page(foodcoop)
    elif 'new supplier' in submitted_form:
        pass

@bottle.route('/<foodcoop>/<supplier>')
def supplier(foodcoop, supplier):
    global logged_in
    if logged_in:
        return supplier_page(supplier)
    else:
        return login_page(foodcoop)

@bottle.route('/download/<supplier>/<filename:path>')
def download(supplier, filename):
    print(filename)
    global logged_in
    if logged_in:
        return bottle.static_file(filename, root="output/" + supplier, download=filename)

@bottle.route("/templates/styles.css")
def send_css(filename='styles.css'):
    return bottle.static_file(filename, root="templates")

bottle.run(host='localhost', port=8080, debug=True, reloader=True)