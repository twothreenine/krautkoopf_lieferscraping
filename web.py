import bottle
import re
import os
import numbers
import json
import importlib
from zipfile import ZipFile
import babel.dates

import base
import foodsoft

foodcoop, foodsoft_url, foodsoft_user, foodsoft_password = foodsoft.read_foodsoft_config()
settings = base.read_settings(foodcoop)
locale = base.read_settings(foodcoop)["default_locale"]
locales = base.read_locales(foodcoop)
# username = foodcoop.capitalize() + "-Mitglied" # placeholder for user
username = locales["base"]["member"].format(foodcoop=foodcoop.capitalize()) # placeholder for user
logged_in = False
messages = []

# def get_locale_string(term, script_name):
#     if term in locales[script_name]:
#         string = locales[script_name][term]
#     elif term in locales["base"]:
#         string = locales["base"][term]
#     else:
#         string = term
#     return string

def get_locale_string(term, script_name, substring="", enforce_return=False):
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

def check_login(submitted_form):
    global logged_in
    if logged_in:
        return True
    elif 'password' in submitted_form:
        password = submitted_form.get('password')
        if password == foodsoft_password:
            logged_in = True
            messages.append("Login erfolgreich.")
            return True
        else:
            messages.append("Login fehlgeschlagen.")
            return False
    else:
        return None

def convert_urls_to_links(text):
    urls = re.findall("http\S*", text)
    for url in urls:
        if "'" in url or "</a>" in url:
            continue
        link = "<a href='{}' target='_blank'>{}</a>".format(url, url)
        text = text.replace(url, link)
    return text

def configuration_link(configuration):
    return bottle.template("<a href='/{{foodcoop}}/{{configuration}}'>{{configuration}}</a>", foodcoop=foodcoop, configuration=configuration)

def display_output_link(configuration, run_name):
    return bottle.template("<a href='/{{foodcoop}}/{{configuration}}/display/{{run_name}}'>{{run_name}}</a>", foodcoop=foodcoop, configuration=configuration, run_name=run_name)

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
    config = base.read_config(foodcoop=foodcoop, configuration=configuration)
    script_name = "script_" + base.read_in_config(config=config, detail="Script name")
    script = importlib.import_module(script_name)
    return script

def run_path(configuration, run_name):
    return os.path.join("data", foodcoop, configuration, run_name)

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
        form_content = f"<input name='origin' value='/{foodcoop}/{configuration}/display/{run_name}' hidden><input type='submit' value='⤓'>"
    progress_bar = '<progress id="run" value="{}" max="100"></progress>'.format(run.completion_percentage)
    return bottle.template("<form action='{{source}}' method='post'>{{!form_content}} {{!affix}} {{!progress_bar}}</form>", source=source, form_content=form_content, affix=output_link, progress_bar=progress_bar)

def all_download_buttons(configuration, run_name):
    content = ""
    path = run_path(configuration, run_name)
    files = list_files(path)
    if len(files) > 1:
        content += bottle.template('templates/download_button.tpl', source=zip_download(configuration, run_name), value="⤓ ZIP", affix="", foodcoop=foodcoop, configuration=configuration, run_name=run_name)
    for file in files:
        source = "/download/data/" + foodcoop + "/" + configuration + "/" + run_name + "/download/" + file
        content += bottle.template('templates/download_button.tpl', source=source, value="⤓ " + file, affix="", foodcoop=foodcoop, configuration=configuration, run_name=run_name)
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
            display_content += bottle.template('templates/{}_content.tpl'.format(display_type), title=title, content=content)
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
        config_content += locales["base"]["manual changes"].format(str(len(config[detail])))
    else:
        config_content += f"<label>{get_locale_string(term=str(detail), substring='name', script_name=script_name, enforce_return=True)}: "
        input_type = "input"
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
                placeholder = "placeholder='" + str(variable.example) + "'"
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
            value = f"value='{value}'"
            config_content += f"<{input_type} name='{detail}' {value} {placeholder} {required}>"
        else:
            config_content += f"<{input_type} name='{detail}' {placeholder} {required}>{value}</{input_type}>"
        config_content += f"</label>{description}"

    return config_content

def add_configuration(submitted_form):
    new_config_name = submitted_form.get('new config name')
    config = base.read_config(foodcoop=foodcoop)
    if new_config_name in config:
        messages.append("Es existiert bereits eine Konfiguration namens " + new_config_name + " für " + foodcoop.capitalize() + ". Bitte wähle einen anderen Namen.")
        return new_configuration_page()
    else:
        base.save_configuration(foodcoop=foodcoop, configuration=new_config_name, new_config={"Script name": submitted_form.get('script name')})
        messages.append("Konfiguration angelegt.")
        script = import_script(configuration=new_config_name)
        config_variables = script.config_variables()
        if config_variables:
            return edit_configuration_page(configuration=new_config_name)
        else:
            return main_page()

def save_configuration_edit(configuration, submitted_form):
    config = base.read_config(foodcoop=foodcoop, configuration=configuration)
    for name in submitted_form:
        if name == "configuration name" or name == "password":
            continue
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
    base.save_configuration(foodcoop=foodcoop, configuration=configuration, new_config=config)
    # TODO: Renaming a configuration sometimes leads to PermissionError: [WinError 5], therefore the input field is disabled for now
    # configuration_name = submitted_form.get('configuration name')
    # if configuration_name != configuration:
    #     renamed_configuration = base.rename_configuration(foodcoop=foodcoop, old_configuration_name=configuration, new_configuration_name=configuration_name)
    #     if renamed_configuration:
    #         messages.append('Konfiguration "{}" erfolgreich in "{}" umbenannt.'.format(configuration, renamed_configuration))
    #     return configuration_name
    # else:
    return configuration

def del_configuration(submitted_form):
    configuration_to_delete = submitted_form.get('delete configuration')
    deleted_configuration = base.delete_configuration(foodcoop, configuration_to_delete)
    if deleted_configuration:
        messages.append(configuration_to_delete + " erfolgreich gelöscht.")
    else:
        messages.append("Löschen von " + configuration_to_delete + " fehlgeschlagen: Konfiguration scheint nicht zu existieren.")
    return main_page()

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

    return bottle.template('templates/main.tpl', messages=read_messages(), base_locales=locales["base"], fc=foodcoop, foodcoop=foodcoop.capitalize(), configurations=content)

def login_page(fc, request_path=None, submitted_form={}):
    submitted_form_content = ""
    for field in submitted_form:
        submitted_form_content += f'<input name="{field}" value="{submitted_form.get(field)}" hidden />'
    if fc == foodcoop:
        if not request_path:
            request_path = "/" + fc
        return bottle.template('templates/login.tpl', messages=read_messages(), request_path=request_path, submitted_form_content=submitted_form_content, foodcoop=foodcoop.capitalize(), foodsoft_user=foodsoft_user)
    else:
        return bottle.template('templates/false_url.tpl', foodcoop=fc)

def configuration_page(configuration):
    config = base.read_config(foodcoop=foodcoop, configuration=configuration)
    script_name = base.read_in_config(config, "Script name")
    script = import_script(configuration=configuration)
    output_content = ""
    outputs = base.get_outputs(foodcoop=foodcoop, configuration=configuration)
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
            config_content += locales["base"]["manual changes"].format(str(len(config[detail])))
        else:
            config_content += get_locale_string(term=str(detail), substring='name', script_name=script_name, enforce_return=True) + ": " + str(config[detail])
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

def run_page(configuration, script, run):
    downloads = all_download_buttons(configuration, run.name)
    script_name = base.read_in_config(base.read_config(foodcoop, configuration), "Script name")

    log_entries = []
    for entry in run.log:
        entry_string = get_locale_string(term=entry.action, script_name=script_name, enforce_return=True)
        if entry.done_by:
            entry_string += f" von {entry.done_by}"
        entry_string += f" am {babel.dates.format_datetime(datetime=entry.datetime, format='short', locale=locale)}"
        log_entries.append(entry_string)
    log_text = ", ".join(log_entries)
    if log_text:
        log_text = log_text[0].upper() + log_text[1:]
        log_text += "."

    continue_content = ""
    for option in run.next_possible_methods:
        option_locales = locales[script_name][option.name]
        inputs = ""
        for ipt in option.inputs:
            inputs = add_input_field(ipt=ipt, script_name=script_name, input_content=inputs)
        continue_content += bottle.template('templates/continue_option.tpl', fc=foodcoop, configuration=configuration, run_name=run.name, option_name=option.name, option_locales=option_locales, inputs=inputs)
    display_content = ""
    display_content += display(path=run.path, display_type="display")
    display_content += display(path=run.path, display_type="details")
    return bottle.template('templates/run.tpl', messages=read_messages(), fc=foodcoop, foodcoop=foodcoop.capitalize(), configuration=configuration, run=run, log_text=log_text, completion_percentage=run.completion_percentage, downloads=downloads, continue_content=continue_content, display_content=display_content)

def edit_configuration_page(configuration):
    config_content = ""
    config = base.read_config(foodcoop=foodcoop, configuration=configuration)
    script_name = base.read_in_config(config, "Script name")
    script = import_script(configuration=configuration)
    config_variables = script.config_variables()
    special_variables = ["Script name", "number of runs to list", "last imported run"]

    if "last imported run" in [c_v.name for c_v in config_variables]:
        runs = base.get_outputs(foodcoop=foodcoop, configuration=configuration)
        if runs:
            runs.reverse()
            config_content += f"<label>{locales['base']['last imported run']}: "
            config_content += "<select name='last imported run'>"
            config_content += f"<option>{locales['base']['none (feminine)']}</option>"
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

    # list of environment variables and whether they are set
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

    number_of_runs_to_list = base.read_in_config(config, "number of runs to list", 5)

    return bottle.template('templates/edit_configuration.tpl', messages=read_messages(), fc=foodcoop, foodcoop=foodcoop.capitalize(), base_locales=locales["base"], configuration=configuration, number_of_runs_to_list=number_of_runs_to_list, config_content=config_content, script_options=script_options(selected_script=config["Script name"]))

def delete_configuration_page(configuration):
    return bottle.template('templates/delete_configuration.tpl', messages=read_messages(), fc=foodcoop, foodcoop=foodcoop.capitalize(), configuration=configuration)

def new_configuration_page():
    return bottle.template('templates/new_configuration.tpl', messages=read_messages(), fc=foodcoop, foodcoop=foodcoop.capitalize(), script_options=script_options())

@bottle.route('/<fc>')
def login(fc):
    if check_login(bottle.request.forms):
        return main_page()
    else:
        return login_page(fc)

@bottle.route('/<fc>', method='POST')
def do_main(fc):
    submitted_form = bottle.request.forms
    if check_login(submitted_form):
        if 'new configuration' in submitted_form:
            return new_configuration_page()
        elif 'new config name' in submitted_form:
            return add_configuration(submitted_form)
        elif 'delete configuration' in submitted_form:
            return del_configuration(submitted_form)
        elif 'logout' in submitted_form:
            global logged_in
            logged_in = False
            messages.append("Logout erfolgreich.")
            return login_page(fc)
        else:
            return main_page()
    else:
        return login_page(fc)

@bottle.route('/<fc>/<configuration>', method='ANY')
def configuration(fc, configuration):
    submitted_form = bottle.request.forms
    if check_login(submitted_form):
        if "Script name" in submitted_form:
            configuration = save_configuration_edit(configuration=configuration, submitted_form=submitted_form)
            messages.append("Änderungen in Konfiguration gespeichert.")
        return configuration_page(configuration)
    else:
        return login_page(fc, bottle.request.path, submitted_form)

@bottle.route('/<fc>/<configuration>/display/<run_name>', method='ANY')
def display_run(fc, configuration, run_name):
    submitted_form = bottle.request.forms
    if check_login(submitted_form):
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
                        files = bottle.request.files.getall(ipt.name)
                        for f in files:
                            print(f.content_type) # TODO: check if mime type matches accepted file types
                        value = [f.file for f in files]
                    elif ipt.accepted_file_types or ipt.input_format == "file":
                        file_object = bottle.request.files.get(ipt.name)
                         # TODO: check if mime type matches accepted file types
                        if file_object:
                            value = file_object.file
                    else:
                        value = submitted_form.get(ipt.name)
                    if value:
                        parameters[ipt.name] = value
            func = getattr(run, method)
            func(**parameters)
            run.save()
            script_name = base.read_in_config(base.read_config(fc, configuration), "Script name")
            messages.append(locales[script_name][method]["name"] + " wurde ausgeführt.")
        return run_page(configuration, script, run)
    else:
        return login_page(fc, bottle.request.path, submitted_form)

@bottle.route('/<fc>/<configuration>/new_run', method='ANY')
def start_script_run(fc, configuration):
    submitted_form = bottle.request.forms
    if check_login(submitted_form):
        script = import_script(configuration=configuration)
        run = script.ScriptRun(foodcoop=foodcoop, configuration=configuration)
        run.save()
        return run_page(configuration, script, run)
    else:
        return login_page(fc, bottle.request.path, submitted_form)

@bottle.route('/<fc>/<configuration>/edit', method='ANY')
def edit_configuration(fc, configuration):
    submitted_form = bottle.request.forms
    if check_login(submitted_form):
        return edit_configuration_page(configuration)
    else:
        return login_page(fc, bottle.request.path)

@bottle.route('/<fc>/<configuration>/delete', method='ANY')
def delete_configuration(fc, configuration):
    submitted_form = bottle.request.forms
    if check_login(submitted_form):
        return delete_configuration_page(configuration)
    else:
        return login_page(fc, bottle.request.path, submitted_form)

@bottle.route('/download/<filename:path>', method='ANY')
def download(filename):
    submitted_form = bottle.request.forms
    if check_login(submitted_form):
        return bottle.static_file(filename, root="", download=filename)
    else:
        dir_array = os.path.normpath(filename).split(os.path.sep)
        fc = dir_array[1]
        return login_page(fc=fc, request_path=submitted_form.get("origin"))

@bottle.route("/templates/styles.css")
def send_css(filename='styles.css'):
    return bottle.static_file(filename, root="templates")

if __name__ == "__main__":
    bottle.run(host='0.0.0.0', port=8080, debug=True, reloader=True)
