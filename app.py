import flask
import re
import os
import copy
import secrets
import numbers
import yaml
import importlib
from zipfile import ZipFile
import babel.dates

import base
import foodsoft

HTTP_METHODS = ['GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'CONNECT', 'OPTIONS', 'TRACE', 'PATCH']

app = flask.Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/' # TODO: generate random key
app.data = {}

def print_data(): # only for debugging
    global app
    print(app.data)

def add_data(value):
    key = secrets.token_hex()
    global app
    app.data[key] = value
    return key

def get_data(key):
    global app
    return app.data.get(key)

def delete_data(key):
    global app
    if app.data.get(key):
        app.data.pop(key)

def get_instance():
    return flask.session["instance"]

def get_settings():
    return base.read_settings(get_instance())

def get_locales(): # TODO: consider user preference?
    return base.read_locales(get_instance())

def get_locale():
    return flask.session["locale"]

def get_foodsoft_connector():
    return get_data(flask.session.get("foodsoft_connector_key"))

def reset_foodsoft_connector():
    if key := flask.session.get("foodsoft_connector_key"):
        delete_data(key)
    flask.session["foodsoft_connector_key"] = None

class Session:
    def __init__(self):
        self.instance = get_instance()
        self.foodsoft_connector = get_foodsoft_connector()
        self.settings = get_settings()
        self.locales = get_locales()
        self.locale = get_locale()

def get_locale_string(term, script_name, substring="", enforce_return=False):
    locales = get_locales()
    if term in locales[script_name] and substring in locales[script_name][term]:
        if substring:
            string = locales[script_name][term][substring]
        else:
            string = locales[script_name][term]
    elif term in locales["base"] and substring in locales["base"][term]:
        if substring:
            string = locales["base"][term][substring]
        else:
            string = locales["base"][term]
    elif substring == "name" and term in locales[script_name]:
        string = locales[script_name][term]
    elif substring == "name" and term in locales["base"]:
        string = locales["base"][term]
    elif enforce_return:
        string = term
    else:
        string = ""
    return string

def switch_to_instance(instance):
    reset_foodsoft_connector()
    flask.session["instance"] = instance
    flask.session["locale"] = get_settings().get("default_locale")

def check_login(submitted_form, cookies, instance):
    user_data = cookies.get("user")
    if user_data:
        user_data = user_data.split("/")
        cookie_instance = user_data[0]
        cookie_email = user_data[1]
        if get_foodsoft_connector():
            if flask.session.get("instance") == instance and instance == cookie_instance:
                return True
    if 'password' in submitted_form:
        switch_to_instance(instance)
        success = None
        feedback = ""
        email = submitted_form.get('email')
        password = submitted_form.get('password')
        foodsoft_address = get_settings().get('foodsoft_url')
        foodsoft_connector = foodsoft.FSConnector(url=foodsoft_address, user=email, password=password)
        foodsoft_connector.add_user_data(workgroups=True)
        if foodsoft_connector._session:
            message = f"Hallo {foodsoft_connector.first_name}!"
            allowed_workgroups = get_settings().get('allowed_workgroups')
            if allowed_workgroups:
                matching_workgroups = [wg for wg in foodsoft_connector.workgroups if wg in allowed_workgroups]
                print(matching_workgroups)
                if matching_workgroups:
                    success = True
                else:
                    success = False
                    message += " Deine Anmeldung ist fehlgeschlagen, da du nicht die erforderlichen Berechtigungen besitzt."
            else:
                success = True
        if success:
            flask.session["foodsoft_connector_key"] = add_data(foodsoft_connector)
            print_data() # TODO: delete this - only for debugging
            flask.session["instance"] = instance
            message += " Deine Anmeldung war erfolgreich."
            flask.flash(message)
            return True
        else:
            reset_foodsoft_connector()
            flask.flash("Login fehlgeschlagen: E-Mail-Adresse und/oder Passwort falsch.")
            return False
    else:
        return None

def convert_urls_to_links(text):
    urls = re.findall(r"http\S*", text)
    for url in urls:
        if "'" in url or "</a>" in url:
            continue
        link = "<a href='{}' target='_blank'>{}</a>".format(url, url)
        text = text.replace(url, link)
    return text

def submitted_form_content(submitted_form, request_path=None):
    submitted_form_content = ""
    if request_path:
        submitted_form_content += f'<input name="request_path" value="{request_path}" hidden />'
    if submitted_form:
        for field in submitted_form:
            submitted_form_content += f'<input name="{field}" value="{submitted_form.get(field)}" hidden />'
    return submitted_form_content

def login_link(instance):
    return flask.render_template('login_link.html', instance=instance)

def configuration_link(configuration):
    return flask.render_template('configuration_link.html', foodcoop=get_instance(), configuration=configuration)

def display_output_link(configuration, run_name):
    return flask.render_template('display_output_link.html', foodcoop=get_instance(), configuration=configuration, run_name=run_name)

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

def import_script(configuration):
    importlib.invalidate_caches()
    config = base.read_config(foodcoop=get_instance(), configuration=configuration)
    script_name = "script_" + base.read_in_config(config=config, detail="Script name")
    script = importlib.import_module(script_name)
    return script

def run_path(configuration, run_name):
    return os.path.join("data", get_instance(), configuration, run_name)

def list_files(path, folder="download"):
    files = []
    files_path = os.path.join(path, folder)
    if os.path.exists(files_path):
        files = [f for f in os.listdir(files_path)]
    return files

def zip_download(configuration, run_name):
    path = run_path(configuration, run_name)
    files = list_files(path)
    zip_filepath = os.path.join(path, configuration + "_" + run_name + ".zip")
    with ZipFile(zip_filepath, 'w') as zipObj:
        for file in files:
            download_filepath = os.path.join(path, "download", file)
            zipObj.write(download_filepath, os.path.basename(download_filepath))
    source = "/download/" + zip_filepath
    return source

def output_link_with_download_button(configuration, script, run_name):
    path = run_path(configuration, run_name)
    run = script.ScriptRun.load(path=path)
    files = list_files(path)
    output_link = display_output_link(configuration, run_name)
    form_content = ""
    source = ""
    if files:
        if len(files) == 1:
            source = "/download/" + run_path(configuration, run_name) + "/download/" + files[0]
        else:
            source = zip_download(configuration, run_name)
        form_content = f"<input name='origin' value='/{get_instance()}/{configuration}/display/{run_name}' hidden><input type='submit' value='⤓'>"
    progress_bar = '<progress id="run" value="{}" max="100"></progress>'.format(run.completion_percentage)
    return flask.render_template('output_link_with_download_button.html', source=source, form_content=form_content, affix=output_link, progress_bar=progress_bar)

def all_download_buttons(configuration, run_name):
    content = ""
    path = run_path(configuration, run_name)
    files = list_files(path)
    if len(files) > 1:
        content += flask.render_template('download_button.html', source=zip_download(configuration, run_name), value="⤓ ZIP", affix="", foodcoop=get_instance(), configuration=configuration, run_name=run_name)
    for file in files:
        source = "/download/data/" + get_instance() + "/" + configuration + "/" + run_name + "/download/" + file
        content += flask.render_template('download_button.html', source=source, value="⤓ " + file, affix="", foodcoop=get_instance(), configuration=configuration, run_name=run_name)
    return content

def display(path, display_type="display"):
    display_content = ""
    file_path = os.path.join(path, display_type)
    if os.path.exists(file_path):
        files = [f for f in os.listdir(file_path)]
        for file in files:
            with open(os.path.join(path, display_type, file), encoding="utf-8") as text_file:
                content = text_file.read()
                content = convert_urls_to_links(content)
                content = content.replace("\n", "<br>")
            title = os.path.splitext(file)[0]
            display_content += flask.render_template('{}_content.html'.format(display_type), title=title, content=content)
    return display_content

def add_input_field(ipt, script_name, input_content):
    if input_content:
        input_content += "<br/>"

    field_type = "input"
    input_type = ""
    input_attributes = ""
    file_types = ",".join(ipt.accepted_file_types)

    if not ipt.input_format:
        if ipt.example:
            if isinstance(ipt.example, numbers.Number):
                input_type = "type='number'"
            elif len(str(ipt.example)) > 20:
                field_type = "textarea"
        elif ipt.accepted_file_types:
            input_type = "type='file'"
            input_attributes = f"accept='{file_types}'"
    elif ipt.input_format == "textarea":
        field_type = "textarea"
    elif ipt.input_format == "file" or ipt.input_format == "files":
        input_type = "type='file'"
        if ipt.accepted_file_types:
            input_attributes = f"accept='{file_types}'"
        if ipt.input_format == "files":
            input_attributes += " multiple"
    else:
        input_type = f"type='{ipt.input_format}'"

    placeholder = ""
    if ipt.example:
        placeholder = f"placeholder='{ipt.example}'"

    required = ""
    if ipt.required:
        required = "required"

    description = get_locale_string(term=str(ipt.name), substring='description', script_name=script_name)
    if description:
        description = f" ({description})"

    input_content += f"<label>{get_locale_string(term=str(ipt.name), substring='name', script_name=script_name, enforce_return=True)}: "
    input_content += f"<{field_type} {input_type} name='{ipt.name}' {placeholder} {required} {input_attributes}></{field_type}>"
    input_content += f"</label>{description}"

    return input_content

def add_config_variable_field(detail, config, config_variables, special_variables, script_name, config_content=""):
    if config_content:
        config_content += "<br/>"
    if str(detail) == "manual changes":
        config_content += get_locales()["base"]["manual changes"].format(str(len(config[detail])))
    else:
        config_content += f"<label>{get_locale_string(term=str(detail), substring='name', script_name=script_name, enforce_return=True)}: "
        input_type = "input type='text'"
        placeholder = ""
        required = ""
        value = ""
        example = None
        description = ""
        if detail in config:
            value = config[detail]
        config_variables_of_this_name = [variable for variable in config_variables if variable.name == detail]
        if config_variables_of_this_name:
            variable = config_variables_of_this_name[0]
            if variable.required:
                required = "required"
            if variable.example:
                placeholder = f'placeholder="{str(variable.example)}"'
                example = variable.example
            description = get_locale_string(term=str(detail), substring='description', script_name=script_name)
            if description:
                description = f" ({description})"

        # determine input type
        if isinstance(example, numbers.Number):
            input_type = "input type='number'"
        elif value:
            if len(str(value)) > 20:
                input_type = "textarea"
        elif example:
            if len(str(example)) > 20:
                input_type = "textarea"

        value = str(value)
        if input_type.startswith("input"):
            if value:
                value = f"value={value}"
            else:
                value = "value=''"
            config_content += f"<{input_type} name='{detail}' {value} {placeholder} {required}>"
        else:
            config_content += f"<{input_type} name='{detail}' {placeholder} {required}>{value}</{input_type}>"
        config_content += f"</label>{description}"

    return config_content

def add_instance(submitted_form):
    new_instance_name = submitted_form.get('new instance name').strip()
    if base.equal_strings_check([new_instance_name], base.find_instances()):
        flask.flash(f"Es existiert bereits eine Instanz namens {new_instance_name}! Bitte wähle einen anderen Namen.")
        return flask.make_response(new_instance_page(submitted_form))
    else:
        settings = {
            "description": submitted_form.get('description'),
            "default_locale": submitted_form.get('locale'),
            "foodsoft_url": submitted_form.get('foodsoft url'),
            "configuration_groups": {}
            }
        base.save_settings(new_instance_name, settings)
        flask.flash("Instanz angelegt.")
        return flask.make_response(login_page(new_instance_name))

def add_configuration(submitted_form):
    new_configuration_name = submitted_form.get('new configuration name').strip()
    if base.equal_strings_check([new_configuration_name], base.find_configurations(foodcoop=get_instance())):
        flask.flash("Es existiert bereits eine Konfiguration namens " + new_configuration_name + " für " + get_instance().capitalize() + ". Bitte wähle einen anderen Namen.")
        return flask.make_response(new_configuration_page())
    else:
        base.save_config(foodcoop=get_instance(), configuration=new_configuration_name, config={"Script name": submitted_form.get('script name')})
        flask.flash("Konfiguration angelegt.")
        script = import_script(configuration=new_configuration_name)
        config_variables = script.config_variables()
        if config_variables:
            return flask.make_response(edit_configuration_page(configuration=new_configuration_name))
        else:
            return flask.make_response(main_page())

def save_configuration_edit(configuration, submitted_form):
    config = base.read_config(foodcoop=get_instance(), configuration=configuration)
    for name in submitted_form:
        if name == "configuration name" or name == "password":
            continue
        value = submitted_form.get(name)
        if value:
            if value.startswith("[") and value.endswith("]"):
                try:
                    value = yaml.safe_load(value)
                except:
                    raise
            elif value.casefold() == "true": # use checkboxes in the form instead of converting strings to booleans
                value = True
            elif value.casefold() == "false":
                value = False
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
    base.save_config(foodcoop=get_instance(), configuration=configuration, config=config)
    # TODO: Renaming a configuration sometimes leads to PermissionError: [WinError 5], therefore the input field is disabled for now
    # configuration_name = submitted_form.get('configuration name')
    # if configuration_name != configuration:
    #     renamed_configuration = base.rename_configuration(foodcoop=get_instance(), old_configuration_name=configuration, new_configuration_name=configuration_name)
    #     if renamed_configuration:
    #         global app
    #         flask.flash('Konfiguration "{}" erfolgreich in "{}" umbenannt.'.format(configuration, renamed_configuration))
    #     return configuration_name
    # else:
    return configuration

def del_configuration(submitted_form):
    configuration_to_delete = submitted_form.get('delete configuration')
    success, feedback = base.delete_configuration(get_instance(), configuration_to_delete)
    if success:
        flask.flash(configuration_to_delete + " erfolgreich gelöscht.")
    elif feedback:
        flask.flash(feedback)
    else:
        flask.flash("Löschen von " + configuration_to_delete + " fehlgeschlagen: Konfiguration scheint nicht zu existieren.")
    return flask.make_response(main_page())

def root_page():
    instances_content = ""
    for instance in base.find_instances():
        instances_content += login_link(instance)
    return flask.render_template('root.html', instances_content=instances_content)

def new_instance_page(submitted_form=None):
    name_value = ""
    description_value = ""
    url_value = ""
    locale_value = ""
    if submitted_form:
        name_value = submitted_form.get("new instance name")
        description_value = submitted_form.get("description")
        url_value = submitted_form.get("foodsoft url")
        locale_value = submitted_form.get("locale")

    locale_options = ""
    available_locales = base.find_available_locales()
    for loc in available_locales:
        selected = ""
        if locale_value == loc:
            selected = " selected"
        locale_options += f"<option{selected}>{loc}</option>"

    return flask.render_template('new_instance.html', name_value=name_value, description_value=description_value, url_value=url_value, locale_options=locale_options)

def main_page():
    content = ""
    for configuration in base.find_configurations(foodcoop=get_instance()):
        if content:
            content += "<br/>"
        content += configuration_link(configuration)

    return flask.render_template('main.html', base_locales=get_locales()["base"], fc=get_instance(), foodcoop=get_instance().capitalize(), configurations=content)

def login_page(fc, request_path=None, submitted_form=None):
    if not request_path:
        request_path = "/" + fc
    if get_foodsoft_connector() and flask.session.get("instance") != fc:
        return flask.make_response(switch_instance_page(fc, request_path, submitted_form))
    else:
        switch_to_instance(fc)
        foodsoft_address = get_settings().get("foodsoft_url", "")
        foodsoft_login_address = foodsoft_address
        if not foodsoft_login_address.endswith("/"):
            foodsoft_login_address += "/"
        foodsoft_login_address += "login"
        description = get_settings().get("description", "")
        return flask.render_template('login.html', request_path=request_path, submitted_form_content=submitted_form_content(submitted_form), foodcoop=get_instance().capitalize(), foodsoft_address=foodsoft_address, foodsoft_login_address=foodsoft_login_address, description=description)

def switch_instance_page(requested_instance, request_path=None, submitted_form=None):
    return flask.render_template('switch_instance.html', requested_instance=requested_instance, current_instance=get_instance(), submitted_form_content=submitted_form_content(submitted_form, request_path))

def configuration_page(configuration):
    config = base.read_config(foodcoop=get_instance(), configuration=configuration)
    script_name = base.read_in_config(config, "Script name")
    script = import_script(configuration=configuration)
    output_content = ""
    outputs = base.get_outputs(foodcoop=get_instance(), configuration=configuration)
    if not outputs:
        output_content += "Keine Ausführungen gefunden."
    outputs.reverse()
    number_of_runs_to_list = base.read_in_config(config, "number of runs to list", 5)
    for index in range(number_of_runs_to_list):
        if index+1 > len(outputs):
            break
        if output_content:
            output_content += "<br/>"
        output_content += output_link_with_download_button(configuration=configuration, script=script, run_name=outputs[index])
    config_content = ""
    for detail in config:
        if config_content:
            config_content += "<br/>"
        if str(detail) == "manual changes":
            config_content += get_locales()["base"]["manual changes"].format(str(len(config[detail])))
        else:
            config_content += get_locale_string(term=str(detail), substring='name', script_name=script_name, enforce_return=True) + ": " + str(config[detail])

    return flask.render_template('configuration.html', fc=get_instance(), foodcoop=get_instance().capitalize(), configuration=configuration, output_content=output_content, config_content=config_content)

def run_page(configuration, script, run):
    downloads = all_download_buttons(configuration, run.name)
    script_name = base.read_in_config(base.read_config(get_instance(), configuration), "Script name")

    log_entries = []
    for entry in run.log:
        entry_string = get_locale_string(term=entry.action, script_name=script_name, enforce_return=True)
        if entry.done_by:
            entry_string += f" von {entry.done_by}"
        entry_string += f" am {babel.dates.format_datetime(datetime=entry.datetime, format='short', locale=get_locale())}"
        log_entries.append(entry_string)
    log_text = ", ".join(log_entries)
    if log_text:
        log_text = log_text[0].upper() + log_text[1:]
        log_text += "."

    continue_content = ""
    for option in run.next_possible_methods:
        option_locales = get_locales()[script_name][option.name]
        inputs = ""
        for ipt in option.inputs:
            inputs = add_input_field(ipt=ipt, script_name=script_name, input_content=inputs)
        continue_content += flask.render_template('continue_option.html', fc=get_instance(), configuration=configuration, run_name=run.name, option_name=option.name, option_locales=option_locales, inputs=inputs)
    display_content = ""
    display_content += display(path=run.path, display_type="display")
    display_content += display(path=run.path, display_type="details")
    return flask.render_template('run.html', fc=get_instance(), foodcoop=get_instance().capitalize(), configuration=configuration, run=run, log_text=log_text, completion_percentage=run.completion_percentage, downloads=downloads, continue_content=continue_content, display_content=display_content)

def edit_configuration_page(configuration):
    config_content = ""
    config = base.read_config(foodcoop=get_instance(), configuration=configuration)
    script_name = base.read_in_config(config, "Script name")
    script = import_script(configuration=configuration)
    config_variables = script.config_variables()
    special_variables = ["Script name", "number of runs to list", "last imported run"]

    if "last imported run" in [c_v.name for c_v in config_variables]:
        runs = base.get_outputs(foodcoop=get_instance(), configuration=configuration)
        if runs:
            runs.reverse()
            config_content += f"<label>{get_locales()['base']['last imported run']}: "
            config_content += "<select name='last imported run'>"
            config_content += f"<option>{get_locales()['base']['none (feminine)']}</option>"
            last_imported_run = base.read_in_config(config, "last imported run", "")
            for run in runs:
                selected = ""
                if run == last_imported_run:
                    selected = " selected"
                config_content += f"<option value='{run}'{selected}>{run}</option>"
            config_content += "</select></label>"

    # variables already set in config
    for detail in config:
        if detail in special_variables:
            continue
        config_content = add_config_variable_field(detail=detail, config=config, config_variables=config_variables, special_variables=special_variables, script_name=script_name, config_content=config_content)

    # variables the script uses which are not yet in config
    for variable in config_variables:
        if variable.name in config or variable.name in special_variables:
            continue
        config_content = add_config_variable_field(detail=variable.name, config=config, config_variables=config_variables, special_variables=special_variables, script_name=script_name, config_content=config_content)

    number_of_runs_to_list = base.read_in_config(config, "number of runs to list", 5)

    return flask.render_template('edit_configuration.html', fc=get_instance(), foodcoop=get_instance().capitalize(), base_locales=get_locales()["base"], configuration=configuration, number_of_runs_to_list=number_of_runs_to_list, config_content=config_content, script_options=script_options(selected_script=config["Script name"]))

def delete_configuration_page(configuration):
    return flask.render_template('delete_configuration.html', fc=get_instance(), foodcoop=get_instance().capitalize(), configuration=configuration)

def new_configuration_page():
    return flask.render_template('new_configuration.html', fc=get_instance(), foodcoop=get_instance().capitalize(), script_options=script_options())

@app.route('/', methods=HTTP_METHODS)
def root():
    submitted_form = flask.request.form
    if 'new instance' in submitted_form:
        return flask.make_response(new_instance_page())
    elif 'new instance name' in submitted_form:
        return add_instance(submitted_form)
    else:
        return flask.make_response(root_page())

@app.get('/<fc>')
def login(fc):
    if check_login(flask.request.form, flask.request.cookies, fc):
        return flask.make_response(main_page())
    else:
        return flask.make_response(login_page(fc))

@app.post('/<fc>')
def do_main(fc):
    submitted_form = flask.request.form
    if 'logout' in submitted_form:
        reset_foodsoft_connector()
        flask.session["instance"] = None
        flask.flash("Logout erfolgreich.")
        request_path = submitted_form.get("request_path")
        if request_path:
            return flask.make_response(login_page(fc, request_path))
        else:
            return flask.make_response(root_page())
    elif check_login(submitted_form, flask.request.cookies, fc):
        if 'new configuration' in submitted_form:
            resp = flask.make_response(new_configuration_page())
        elif 'new configuration name' in submitted_form:
            resp = flask.make_response(add_configuration(submitted_form))
        elif 'delete configuration' in submitted_form:
            resp = flask.make_response(del_configuration(submitted_form))
        else:
            resp = flask.make_response(main_page())
        resp.set_cookie("user", f"{fc}/{get_foodsoft_connector().user}")
        return resp
    else:
        return flask.make_response(login_page(fc))

@app.route('/<fc>/<configuration>', methods=HTTP_METHODS)
def configuration(fc, configuration):
    submitted_form = flask.request.form
    if check_login(submitted_form, flask.request.cookies, fc):
        if "Script name" in submitted_form:
            configuration = save_configuration_edit(configuration=configuration, submitted_form=submitted_form)
            flask.flash("Änderungen in Konfiguration gespeichert.")
        return flask.make_response(configuration_page(configuration))
    else:
        return flask.make_response(login_page(fc, flask.request.full_path, submitted_form))

@app.route('/<fc>/<configuration>/display/<run_name>', methods=HTTP_METHODS)
def display_run(fc, configuration, run_name):
    submitted_form = flask.request.form
    if check_login(submitted_form, flask.request.cookies, fc):
        importlib.invalidate_caches()
        script = import_script(configuration=configuration)
        path = run_path(configuration, run_name)
        run = script.ScriptRun.load(path=path)
        if "method" in submitted_form:
            method = submitted_form.get('method')
            parameters = {}
            # script_method = getattr(script, method)
            script_method = [sm for sm in run.next_possible_methods if sm.name == method][0]
            if script_method.inputs:
                for ipt in script_method.inputs:
                    value = None
                    if ipt.input_format == "files":
                        files = flask.request.files.getall(ipt.name)
                        for f in files:
                            print(f.content_type) # TODO: check if mime type matches accepted file types & TODO: test multi-file upload
                        value = copy.deepcopy(files)
                    elif ipt.accepted_file_types or ipt.input_format == "file":
                        file_object = flask.request.files.get(ipt.name)
                         # TODO: check if mime type matches accepted file types
                        if file_object:
                            value = file_object
                    else:
                        value = submitted_form.get(ipt.name)
                    if value:
                        parameters[ipt.name] = value
            func = getattr(run, method)
            func(Session(), **parameters)
            run.save()
            script_name = base.read_in_config(base.read_config(fc, configuration), "Script name")
            flask.flash(get_locales()[script_name][method]["name"] + " wurde ausgeführt.")
        return flask.make_response(run_page(configuration, script, run))
    else:
        return flask.make_response(login_page(fc, flask.request.full_path, submitted_form))

@app.route('/<fc>/<configuration>/new_run', methods=HTTP_METHODS)
def start_script_run(fc, configuration):
    submitted_form = flask.request.form
    if check_login(submitted_form, flask.request.cookies, fc):
        importlib.invalidate_caches()
        script = import_script(configuration=configuration)
        run = script.ScriptRun(foodcoop=get_instance(), configuration=configuration)
        run.save()
        return flask.make_response(run_page(configuration, script, run))
    else:
        return flask.make_response(login_page(fc, flask.request.full_path, submitted_form))

@app.route('/<fc>/<configuration>/edit', methods=HTTP_METHODS)
def edit_configuration(fc, configuration):
    submitted_form = flask.request.form
    if check_login(submitted_form, flask.request.cookies, fc):
        return flask.make_response(edit_configuration_page(configuration))
    else:
        return flask.make_response(login_page(fc, flask.request.full_path))

@app.route('/<fc>/<configuration>/delete', methods=HTTP_METHODS)
def delete_configuration(fc, configuration):
    submitted_form = flask.request.form
    if check_login(submitted_form, flask.request.cookies, fc):
        return flask.make_response(delete_configuration_page(configuration))
    else:
        return flask.make_response(login_page(fc, flask.request.full_path, submitted_form))

@app.route('/download/<path:filepath>', methods=HTTP_METHODS)
def download(filepath):
    submitted_form = flask.request.form
    dir_array = os.path.normpath(filepath).split(os.path.sep)
    fc = dir_array[1]
    if check_login(submitted_form, flask.request.cookies, fc):
        return flask.send_from_directory(directory="", path=filepath)
    else:
        return flask.make_response(login_page(fc=fc, request_path=submitted_form.get("origin")))
