import bottle
import re
import base
import os
import numbers
import json
from zipfile import ZipFile

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

def configuration_link(configuration):
    return bottle.template("<a href='/{{foodcoop}}/{{configuration}}'>{{configuration}}</a>", foodcoop=foodcoop, configuration=configuration)

def display_output_link(configuration, run):
    return bottle.template("<a href='/{{foodcoop}}/{{configuration}}/display/{{run}}'>{{run}}</a>", foodcoop=foodcoop, configuration=configuration, run=run)

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

def script_options(selected_script=None):
    generic_scripts, foodcoop_scripts = available_scripts()
    script_options = "<option value=''>Skript auswählen</option>"
    for script in generic_scripts:
        value = script[0] + "_" + script[1]
        selected = ""
        if value == selected_script:
            selected = "selected"
        script_options += "<option value='{}' {}>{}</option>".format(value, selected, script[1])
    for script in foodcoop_scripts:
        value = script[0] + "_" + script[1]
        selected = ""
        if value == selected_script:
            selected = "selected"
        script_options += "<option value='{}' {}>{}</option>".format(value, selected, script[0].capitalize() + ": " + script[1])
    return script_options

def get_script_name(configuration):
    config = base.read_config(foodcoop=foodcoop, configuration=configuration, ensure_subconfig="Script name")
    script = "script_" + config["Script name"]
    return script

def run_path(configuration, run):
    return os.path.join("output", foodcoop, configuration, run)

def list_files(path, folder="download"):
    return [f for f in os.listdir(os.path.join(path, folder))]

def zip_download(configuration, run):
    path = run_path(configuration, run)
    files = list_files(path)
    zip_filepath = os.path.join(path, configuration + "_" + run + ".zip")
    if not os.path.isfile(zip_filepath):
        with ZipFile(zip_filepath, 'w') as zipObj:
            for file in files:
                download_filepath = os.path.join(path, "download", file)
                zipObj.write(download_filepath, os.path.basename(download_filepath))
    source = "/download/" + zip_filepath
    return source

def output_link_with_download_button(configuration, run):
    path = run_path(configuration, run)
    files = list_files(path)
    output_link = display_output_link(configuration, run)
    if files:
        if len(files) == 1:
            source = "/download/output/" + foodcoop + "/" + configuration + "/" + run + "/download/" + files[0]
        else:
            source = zip_download(configuration, run)
        return bottle.template('templates/download_button.tpl', source=source, value="⤓", affix=" " + output_link)
    else:
        return output_link

def all_download_buttons(configuration, run):
    content = ""
    path = run_path(configuration, run)
    files = [f for f in os.listdir(os.path.join(path, "download"))]
    if len(files) > 1:
        content += bottle.template('templates/download_button.tpl', source=zip_download(configuration, run), value="⤓ ZIP", affix="")
    for file in files:
        source = "/download/output/" + foodcoop + "/" + configuration + "/" + run + "/download/" + file
        content += bottle.template('templates/download_button.tpl', source=source, value="⤓ " + file, affix="")
    return content

def display_content(path, display_type="display"):
    display_content = ""
    file_path = os.path.join(path, display_type)
    if os.path.exists(file_path):
        files = [f for f in os.listdir(file_path)]
        for file in files:
            with open(os.path.join(path, display_type, file), encoding="utf-8") as text_file:
                content = text_file.read().replace("\n", "<br>")
            title = os.path.splitext(file)[0]
            display_content += bottle.template('templates/{}_content.tpl'.format(display_type), title=title, content=content)
    return display_content

def add_configuration(submitted_form):
    new_config_name = submitted_form.get('new config name')
    config = base.read_config(foodcoop=foodcoop)
    if new_config_name in config:
        messages.append("Es existiert bereits eine Konfiguration namens " + new_config_name + " für " + foodcoop.capitalize() + ". Bitte wähle einen anderen Namen.")
        return new_configuration_page()
    else:
        base.save_configuration(foodcoop=foodcoop, configuration=new_config_name, configuration_config={"Script name": submitted_form.get('script name'), "Foodsoft supplier ID": submitted_form.get('foodsoft supplier ID')})
        messages.append("Konfiguration angelegt.")
        script = __import__(get_script_name(configuration=new_config_name))
        config_variables = script.config_variables()
        if config_variables:
            return edit_configuration_page(configuration=new_config_name)
        else:
            return main_page()

def save_configuration_edit(configuration, submitted_form):
    config = base.read_config(foodcoop=foodcoop, configuration=configuration)
    for name in submitted_form:
        value = submitted_form.get(name)
        if value:
            if value.startswith("[") and value.endswith("]"):
                try:
                    value = json.loads(value)
                except:
                    raise
            else:
                try:
                    value = int(value)
                except ValueError:
                    pass
                except:
                    raise
            config[name] = value
        elif name in config:
            config.pop(name)
    base.save_configuration(foodcoop=foodcoop, configuration=configuration, configuration_config=config)

def main_page():
    content = ""
    config = base.read_config(foodcoop=foodcoop)
    configurations = [x for x in config]
    if configurations:
        content += configuration_link(configurations[0])
        if "note" in configurations[0]:
            content += " (" + configurations[0]["note"] + ")"
    if len(configurations) > 1:
        for configuration in configurations[1:]:
            content += "<br/>" + configuration_link(configuration)
            if "note" in configuration:
                content += " (" + configuration["note"] + ")"

    return bottle.template('templates/main.tpl', messages=read_messages(), fc=foodcoop, foodcoop=foodcoop.capitalize(), configurations=content)

def login_page(fc):
    if fc == foodcoop:
        return bottle.template('templates/login.tpl', messages=read_messages(), fc=foodcoop, foodcoop=foodcoop.capitalize(), foodsoft_user=foodsoft_user)
    else:
        return bottle.template('templates/false_url.tpl', foodcoop=fc)

def configuration_page(configuration):
    output_content = ""
    outputs = base.get_outputs(foodcoop=foodcoop, configuration=configuration)
    if not outputs:
        output_content += "Keine Ausführungen gefunden."
    outputs.reverse()
    for index in range(5):
        if index+1 > len(outputs):
            break
        if output_content:
            output_content += "<br/>"
        output_content += output_link_with_download_button(configuration=configuration, run=outputs[index])
    config_content = ""
    config = base.read_config(foodcoop=foodcoop, configuration=configuration)
    for detail in config:
        if config_content:
            config_content += "<br/>"
        config_content += str(detail) + ": "
        if str(detail) == "manual changes":
            config_content += str(len(config[detail])) + " manual changes"
        else:
            config_content += str(config[detail])
    script = __import__(get_script_name(configuration=configuration))
    environment_variables = script.environment_variables()
    for variable in environment_variables:
        if config_content:
            config_content += "<br/>"
        if variable.name in os.environ:
            if variable.required:
                config_content += "✅ " + variable.name
            else:
                config_content += "✓ " + variable.name
        elif variable.required:
            config_content += "❌ " + variable.name
    return bottle.template('templates/configuration.tpl', messages=read_messages(), fc=foodcoop, foodcoop=foodcoop.capitalize(), configuration=configuration, output_content=output_content, config_content=config_content)

def display_run_page(configuration, run):
    content = ""
    path = run_path(configuration, run)
    downloads = all_download_buttons(configuration, run)
    content += display_content(path=path, display_type="display")
    content += display_content(path=path, display_type="details")
    return bottle.template('templates/display_run.tpl', messages=read_messages(), fc=foodcoop, foodcoop=foodcoop.capitalize(), configuration=configuration, run=run, downloads=downloads, content=content)

def edit_configuration_page(configuration):
    config_content = ""
    config = base.read_config(foodcoop=foodcoop, configuration=configuration)
    script = __import__(get_script_name(configuration=configuration))
    config_variables = script.config_variables()
    for detail in config:
        if detail == "Script name" or detail == "Foodsoft supplier ID":
            continue
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
            config_variables_of_this_name = [variable for variable in config_variables if variable.name == detail]
            if config_variables_of_this_name:
                variable = config_variables_of_this_name[0]
                if variable.required:
                    required = "required"
                if variable.example:
                    placeholder = "placeholder='" + str(variable.example) + "'"
            value = "value='" + str(config[detail]) + "'"
            config_content += "<input name='{}' type='{}' {} {} {}>".format(detail, input_type, value, placeholder, required)

    for variable in config_variables:
        if variable.name in config:
            continue
        if config_content:
            config_content += "<br/>"
        config_content += str(variable.name) + ": "
        input_type = "text"
        placeholder = ""
        required = ""
        description = ""
        if variable.example:
            if isinstance(variable.example, numbers.Number):
                input_type = "number"
            placeholder = "placeholder='" + str(variable.example) + "'"
        if variable.required:
            required = "required"
        if variable.description:
            description = " ({})".format(variable.description)
        config_content += "<input name='{}' type='{}' {} {}>{}".format(variable.name, input_type, placeholder, required, description)

    environment_variables = script.environment_variables()
    if environment_variables:
        config_content += "<h2>Umgebungsvariablen</h2><p>Diese können nur manuell gesetzt werden.</p>"
    for variable in environment_variables:
        required = False
        if variable.required:
            required = True
        if variable.name in os.environ:
            if required:
                mark = "✅"
            else:
                mark = "✓"
        elif required:
            mark = "❌"
        else:
            mark = "✗"
        config_content += mark + " " + variable.name
        if required:
            config_content += " (benötigt)"
        if variable.example:
            config_content += " (Beispiel: " + variable.example + ")"
        config_content += "<br/>"

    foodsoft_supplier_id = ""
    if "Foodsoft supplier ID" in config:
        foodsoft_supplier_id = config["Foodsoft supplier ID"]
    return bottle.template('templates/edit_configuration.tpl', messages=read_messages(), fc=foodcoop, foodcoop=foodcoop.capitalize(), configuration=configuration, config_content=config_content, script_options=script_options(selected_script=config["Script name"]), fs_supplier_id=foodsoft_supplier_id)

def new_configuration_page():
    return bottle.template('templates/new_configuration.tpl', messages=read_messages(), fc=foodcoop, foodcoop=foodcoop.capitalize(), script_options=script_options())

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
    elif logged_in and 'new configuration' in submitted_form:
        return new_configuration_page()
    elif logged_in and 'new config name' in submitted_form:
        return add_configuration(submitted_form)

@bottle.route('/<fc>/<configuration>')
def configuration(fc, configuration):
    global logged_in
    if logged_in:
        return configuration_page(configuration)
    else:
        return login_page(fc)

@bottle.route('/<fc>/<configuration>/display/<run>')
def display_run(fc, configuration, run):
    global logged_in
    if logged_in:
        return display_run_page(configuration, run)
    else:
        return login_page(fc)

@bottle.route('/<fc>/<configuration>', method='POST')
def save_configuration(fc, configuration):
    global logged_in
    if logged_in:
        save_configuration_edit(configuration=configuration, submitted_form=bottle.request.forms)
        messages.append("Änderungen in Konfiguration gespeichert.")
        return configuration_page(configuration)
    else:
        return login_page(fc)

@bottle.route('/<fc>/<configuration>/run')
def run_script(fc, configuration):
    global logged_in
    if logged_in:
        script = __import__(get_script_name(configuration=configuration))
        script.run(foodcoop=foodcoop, configuration=configuration)
        messages.append("Skript erfolgreich ausgeführt.")
        return configuration_page(configuration)
    else:
        return login_page(fc)

@bottle.route('/<fc>/<configuration>/edit')
def edit_configuration(fc, configuration):
    global logged_in
    if logged_in:
        return edit_configuration_page(configuration)
    else:
        return login_page(fc)

@bottle.route('/download/<filename:path>')
def download(filename):
    global logged_in
    if logged_in:
        return bottle.static_file(filename, root="", download=filename)
    else:
        return login_page(fc)

@bottle.route("/templates/styles.css")
def send_css(filename='styles.css'):
    return bottle.static_file(filename, root="templates")

if __name__ == "__main__":
    bottle.run(host='localhost', port=8080, debug=True, reloader=True)