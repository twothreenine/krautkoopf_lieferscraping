import bottle
import re
import base
import os
import numbers

foodcoop, foodsoft_url, foodsoft_user, foodsoft_password = base.read_foodsoft_config()
logged_in = False
messages = []

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
    return bottle.template("<a href='/{{foodcoop}}/{{supplier}}'>{{supplier}}</a>", foodcoop=foodcoop, supplier=supplier)

def available_scripts():
    script_files = [f for f in os.listdir() if f.startswith("script_") and f.endswith(".py")]
    generic_scripts = []
    foodcoop_scripts = []
    for f in script_files:
        f = f.replace("script_", "").replace(".py", "")
        f_parts = f.split("_", 1)
        if f_parts[0] == "generic":
            generic_scripts.append(f_parts)
        else:
            foodcoop_scripts.append(f_parts)
    return generic_scripts, foodcoop_scripts

def get_script_name(supplier):
    config = base.read_config(foodcoop=foodcoop, supplier=supplier, ensure_subconfig="Script name")
    script = "script_" + config["Script name"]
    return script

def output_download_button(supplier, output):
    source = "/download/" + supplier + "/" + output
    # source = "/download/Notizen.txt"
    return "<a href='{}' class='button' download>⤓</a> ".format(source)

def add_supplier(submitted_form):
    new_config_name = submitted_form.get('new config name')
    config = base.read_config(foodcoop=foodcoop)
    if new_config_name in config:
        messages.append("Es existiert bereits eine Konfiguration namens " + new_config_name + " für " + foodcoop.capitalize() + ". Bitte wähle einen anderen Namen.")
        return new_supplier_page()
    else:
        base.save_supplier_config(foodcoop=foodcoop, supplier=new_config_name, supplier_config={"Script name": submitted_form.get('script name'), "Foodsoft supplier ID": submitted_form.get('foodsoft supplier ID')})
        messages.append("Konfiguration angelegt.")
        script = __import__(get_script_name(supplier=new_config_name))
        config_variables = script.config_variables()
        if config_variables:
            return edit_supplier_page(supplier=new_config_name)
        else:
            return main_page()

def main_page():
    content = ""
    config = base.read_config(foodcoop=foodcoop)
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

    return bottle.template('templates/main.tpl', messages=read_messages(), fc=foodcoop, foodcoop=foodcoop.capitalize(), suppliers=content)

def login_page(fc):
    if fc == foodcoop:
        return bottle.template('templates/login.tpl', messages=read_messages(), fc=foodcoop, foodcoop=foodcoop.capitalize(), foodsoft_user=foodsoft_user)
    else:
        return bottle.template('templates/false_url.tpl', foodcoop=fc)

def supplier_page(supplier):
    output_content = ""
    outputs = base.get_outputs(foodcoop=foodcoop, supplier=supplier)
    if not outputs:
        output_content += "Keine CSVs vorhanden."
    outputs.reverse()
    for index in range(5):
        if index+1 > len(outputs):
            break
        if output_content:
            output_content += "<br/>"
        output_content += output_download_button(supplier=supplier, output=outputs[index]) + str(outputs[index])
    config_content = ""
    config = base.read_config(foodcoop=foodcoop, supplier=supplier)
    for detail in config:
        if config_content:
            config_content += "<br/>"
        config_content += str(detail) + ": "
        if str(detail) == "manual changes":
            config_content += str(len(config[detail])) + " manual changes"
        else:
            config_content += str(config[detail])
    return bottle.template('templates/supplier.tpl', messages=read_messages(), fc=foodcoop, foodcoop=foodcoop.capitalize(), supplier=supplier, output_content=output_content, config_content=config_content)

def edit_supplier_page(supplier):
    config_content = ""
    config = base.read_config(foodcoop=foodcoop, supplier=supplier)
    script = __import__(get_script_name(supplier=supplier))
    config_variables = script.config_variables()
    for detail in config:
        if config_content:
            config_content += "<br/>"
        config_content += str(detail) + ": "
        if str(detail) == "manual changes":
            config_content += str(len(config[detail])) + " manual changes"
        else:
            if isinstance(config[detail], numbers.Number):
                input_type = "number"
            else:
                input_type = "text"
            placeholder = ""
            required = ""
            value = ""
            if detail in config_variables:
                if "required" in config_variables[detail]:
                    if config_variables[detail]["required"]:
                        required = "required"
                if "example" in config_variables[detail]:
                    if config_variables[detail]["example"]:
                        placeholder = "placeholder='" + str(config_variables[detail]["example"]) + "'"
            if config[detail]:
                value = "value='" + str(config[detail]) + "'"
            config_content += "<input name='{}' type='{}' {} {} {}>".format(detail, input_type, value, placeholder, required)
    return bottle.template('templates/edit_supplier.tpl', messages=read_messages(), fc=foodcoop, foodcoop=foodcoop.capitalize(), supplier=supplier, config_content=config_content)

def new_supplier_page():
    generic_scripts, foodcoop_scripts = available_scripts()
    script_options = "<option value=''>Skript auswählen</option>"
    for script in generic_scripts:
        script_options += "<option value='{}'>{}</option>".format(script[0] + "_" + script[1], script[1])
    for script in foodcoop_scripts:
        script_options += "<option value='{}'>{}</option>".format(script[0] + "_" + script[1], script[0].capitalize() + ": " + script[1])
    return bottle.template('templates/new_supplier.tpl', messages=read_messages(), fc=foodcoop, foodcoop=foodcoop.capitalize(), script_options=script_options)

@bottle.route('/<fc>')
def login(fc):
    global logged_in
    if logged_in:
        return main_page()
    else:
        return login_page(fc)

@bottle.route('/<fc>', method='POST')
def do_main(fc):
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
            return login_page(fc)
    elif 'logout' in submitted_form:
        logged_in = False
        messages.append("Logout erfolgreich.")
        return login_page(fc)
    elif logged_in and 'new supplier' in submitted_form:
        return new_supplier_page()
    elif logged_in and 'new config name' in submitted_form:
        return add_supplier(submitted_form)

@bottle.route('/<fc>/<supplier>')
def supplier(fc, supplier):
    global logged_in
    if logged_in:
        return supplier_page(supplier)
    else:
        return login_page(fc)

@bottle.route('/<fc>/<supplier>/run')
def run_script(fc, supplier):
    global logged_in
    if logged_in:
        script = __import__(get_script_name(supplier=supplier))
        script.run(foodcoop=foodcoop, supplier=supplier)
        messages.append("Skript erfolgreich ausgeführt.")
        return supplier_page(supplier)
    else:
        return login_page(fc)

@bottle.route('/<fc>/<supplier>/edit')
def edit_supplier(fc, supplier):
    global logged_in
    if logged_in:
        return edit_supplier_page(supplier)
    else:
        return login_page(fc)

@bottle.route('/download/<supplier>/<filename:path>')
def download(supplier, filename):
    print(filename)
    global logged_in
    if logged_in:
        return bottle.static_file(filename, root="output/" + supplier, download=filename)
    else:
        return login_page(fc)

@bottle.route("/templates/styles.css")
def send_css(filename='styles.css'):
    return bottle.static_file(filename, root="templates")

if __name__ == "__main__":
    bottle.run(host='localhost', port=8080, debug=True, reloader=True)