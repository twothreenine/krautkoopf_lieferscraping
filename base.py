import os
import shutil
import yaml
import datetime
import dill
from natsort import natsorted

class Run:
    """
    An instance of a script execution.
    """
    def __init__(self, foodcoop, configuration, log=None, name="", next_possible_methods=None):
        self.path, self.name = prepare_output(foodcoop=foodcoop, configuration=configuration, name=name)
        self.foodcoop = foodcoop
        self.configuration = configuration
        if log:
            self.log = log
        else:
            self.log = []
        if next_possible_methods:
            self.next_possible_methods = next_possible_methods
        else:
            self.next_possible_methods = []
        self.completion_percentage = 0

    def save(self):
        file_path = os.path.join(self.path, "run.obj")
        with open(file_path, 'wb') as file:
            dill.dump(self, file)

    @classmethod
    def load(cls, path):
        with open(os.path.join(path, "run.obj"), 'rb') as file:
            try:
                return dill.load(file)
            except ModuleNotFoundError:
                return None

class ScriptMethod:
    """
    A callable method/function in a script.
    Create ScriptMethod instances for all methods which should be callable by the user at some point,
    and put them into next_possible_methods at the end of a method after which they should be callable.
    """
    def __init__(self, name, inputs=None):
        self.name = name
        if inputs:
            self.inputs = inputs
        else:
            self.inputs = []

class LogEntry:
    """
    An entry of a run's log: What has been done by whom at what date and time.
    """
    def __init__(self, action, done_by=""):
        self.action = action
        self.done_by = done_by
        self.datetime = datetime.datetime.now()

class Variable:
    """
    A variable for a script, either drawn from the config file or the environment variables.
    """
    def __init__(self, name, required=False, example=None, description=""):
        self.name = name
        self.required = required
        self.example = example
        self.description = description

class Input:
    """
    A variable for a script which has to be entered anew each time.
    """
    def __init__(self, name, required=False, input_format="", accepted_file_types=None, example=None, description=""):
        self.name = name
        self.required = required
        self.input_format = input_format # "" (auto), "textarea", "file", "files"; and html input types like "text", "number", ...
        if accepted_file_types:
            self.accepted_file_types = accepted_file_types # for example [".csv"], or [] for all
        else:
            self.accepted_file_types = []
        self.example = example # if not a file
        self.description = description

class Category:
    """
    Nestable categories e.g. for articles, for usage within a script.
    """
    def __init__(self, number=None, name="", subcategories=None):
        self.number = number
        self.name = name
        if subcategories:
            self.subcategories = subcategories
        else:
            self.subcategories = []

def prepare_string_for_comparison(string, case_sensitive, strip):
    if not case_sensitive:
        string = string.casefold()
    if strip:
        string = string.strip()
    return string

def equal_strings_check(list1, list2, case_sensitive=False, strip=True):
    # compares strings of two lists for matches and returns list of matching strings
    matches = []
    compare_list1 = [prepare_string_for_comparison(string, case_sensitive, strip) for string in list1]
    compare_list2 = [prepare_string_for_comparison(string, case_sensitive, strip) for string in list2]

    for string in compare_list1:
        if string in compare_list2:
            matches.append(list1[compare_list1.index(string)])
    return matches

def containing_strings_check(list1, list2, case_sensitive=False, strip=True):
    # checks if any string of list1 contains any string of list2 and returns list of matching strings of list2
    matches = []
    compare_list1 = [prepare_string_for_comparison(string, case_sensitive, strip) for string in list1]
    compare_list2 = [prepare_string_for_comparison(string, case_sensitive, strip) for string in list2]

    for string in compare_list1:
        for query_string in compare_list2:
            if query_string in string:
                matches.append(list2[compare_list2.index(query_string)])
    return matches

def startswith_strings_check(list1, list2, case_sensitive=False, strip=True):
    # checks if any string of list1 starts with any string of list2 and returns list of matching strings of list2
    matches = []
    compare_list1 = [prepare_string_for_comparison(string, case_sensitive, strip) for string in list1]
    compare_list2 = [prepare_string_for_comparison(string, case_sensitive, strip) for string in list2]

    for string in compare_list1:
        for query_string in compare_list2:
            if string.startswith(query_string):
                matches.append(list2[compare_list2.index(query_string)])
    return matches

def endswith_strings_check(list1, list2, case_sensitive=False, strip=True):
    # checks if any string of list1 ends with any string of list2 and returns list of matching strings of list2
    matches = []
    compare_list1 = [prepare_string_for_comparison(string, case_sensitive, strip) for string in list1]
    compare_list2 = [prepare_string_for_comparison(string, case_sensitive, strip) for string in list2]

    for string in compare_list1:
        for query_string in compare_list2:
            if string.endswith(query_string):
                matches.append(list2[compare_list2.index(query_string)])
    return matches

def replace_in_string(string: str, strings_to_replace: dict) -> str:
    # strings_to_replace must be a dictionary of {"string to replace": "by another string"}
    for string_tuple in strings_to_replace.items():
        string = string.replace(string_tuple[0], string_tuple[1])
    return string

def remove_double_strings_loop(text, string, description=None, number_of_runs=100):
    loop_count = 0
    while string+string in text:
        text = text.replace(string+string, string)
        loop_count += 1
        if loop_count > number_of_runs:
            if not description:
                description = "'" + string + "'"
            print("\nLoop to replace double " + description + " ran " + number_of_runs + " times for following text:")
            print(text)
            break
    return text

def find_available_locales():
    available_locales = []
    for package in os.listdir("locales"):
        package_path = os.path.join("locales", package)
        if not os.path.isdir(package_path):
            continue
        for file in [f for f in os.listdir(package_path) if os.path.isfile(os.path.join(package_path, f))]:
            if file.endswith(".yaml"):
                locale = file.replace(".yaml", "")
                if locale not in available_locales:
                    available_locales.append(locale)
    return available_locales

def find_instances():
    root_path = "data"
    if os.path.isdir(root_path):
        return [d for d in os.listdir(root_path) if os.path.isfile(os.path.join(root_path, d, "settings.yaml"))]
    else:
        return []

def find_configurations(foodcoop):
    root_path = os.path.join("data", foodcoop)
    return [d for d in os.listdir(root_path) if os.path.isdir(os.path.join(root_path, d))]

def read_config(foodcoop, configuration):
    filename = os.path.join("data", foodcoop, configuration, "config.yaml")
    if os.path.isfile(filename):
        with open(filename, encoding="UTF8") as yaml_file:
            configuration = yaml.safe_load(yaml_file)
    else:
        configuration = {}
    return configuration

def save_config(foodcoop, configuration, config):
    config_path = os.path.join("data", foodcoop, configuration)
    os.makedirs(config_path, exist_ok=True)
    filename = os.path.join(config_path, "config.yaml")
    with open(filename, "w", encoding="UTF8") as yaml_file:
        yaml.safe_dump(config, yaml_file, allow_unicode=True, indent=4, sort_keys=False)

def set_config_detail(foodcoop, configuration, detail, value):
    config = read_config(foodcoop, configuration)
    config[detail] = value
    save_config(foodcoop, configuration, config)

def rename_configuration(foodcoop, old_configuration_name, new_configuration_name):
    """
    Disabled for now, see app.py for explanation.
    TODO: consider run to be None (run.load changed)
    """
    configurations = find_configurations(foodcoop)
    if old_configuration_name in configurations:
        # rename folder
        existing_output_path = output_path(foodcoop, old_configuration_name)
        new_output_path = output_path(foodcoop, new_configuration_name)
        if os.path.exists(new_output_path): # TODO: ask if user really wants to merge configurations and which config.yaml should be kept; then keep that config.yaml resp. overwrite it, instead of creating config.yaml*
            for entry in os.scandir(existing_output_path):
                new_entry_name = entry.name
                while os.path.exists(os.path.join(new_output_path, new_entry_name)):
                    new_entry_name += "*"
                os.rename(os.path.join(existing_output_path, entry.name), os.path.join(new_output_path, new_entry_name))
            os.rmdir(existing_output_path)
        else:
            os.rename(existing_output_path, new_output_path)

        # update path attribute in run objects
        run_folders = [d for d in os.listdir(new_output_path) if os.path.isdir(os.path.join(new_output_path, d))]
        for run_folder in run_folders:
            run = run.load(path=os.path.join(new_output_path, run_folder))
            run.path = new_output_path
            run.save()

        return new_configuration_name
    else:
        return None

def delete_configuration(foodcoop, configuration):
    configuration_path = os.path.join("data", foodcoop, configuration)
    success = None
    feedback = None
    if os.path.exists(configuration_path):
        try:
            shutil.rmtree(configuration_path)
            success = True
        except OSError as e:
            success = False
            feedback = f"Error: {configuration_path} : {e.strerror}"
    return success, feedback

def read_settings(foodcoop):
    settings_path = os.path.join("data", foodcoop)
    os.makedirs(settings_path, exist_ok=True)
    filename = os.path.join(settings_path, "settings.yaml")
    if os.path.isfile(filename):
        with open(filename, encoding="UTF8") as yaml_file:
            settings = yaml.safe_load(yaml_file)
    else:
        settings = {
            "default_locale": "de_AT",
            "configuration_groups": {
            }
        }
    return settings

def save_settings(foodcoop, settings):
    settings_path = os.path.join("data", foodcoop)
    os.makedirs(settings_path, exist_ok=True)
    filename = os.path.join(settings_path, "settings.yaml")
    with open(filename, "w", encoding="UTF8") as yaml_file:
        yaml.safe_dump(settings, yaml_file, allow_unicode=True, indent=4, sort_keys=False)

def set_setting(foodcoop, setting, value):
    settings = read_settings(foodcoop)
    settings[setting] = value
    save_settings(foodcoop, settings)

def read_locales(foodcoop, locale=None):
    if not locale:
        locale = read_settings(foodcoop)["default_locale"]
    locales = {}
    for package in os.listdir("locales"):
        if not os.path.isdir(os.path.join("locales", package)):
            continue
        if os.path.isfile(os.path.join("locales", package, locale)):
            locale_package = locale + ".yaml"
        elif os.path.isfile(os.path.join("locales", package, "en")):
            locale_package = "en.yaml"
        else:
            locale_package = next(iter(os.listdir(os.path.join("locales", package))))
            if not locale_package:
                continue
        with open(os.path.join("locales", package, locale_package), encoding="UTF8") as yaml_file:
            locales[package] = yaml.safe_load(yaml_file)
    return locales

def output_path(foodcoop, configuration):
    return os.path.join("data", foodcoop, configuration)

def get_outputs(foodcoop, configuration):
    path = output_path(foodcoop, configuration)
    if os.path.exists(path):
        return [d for d in natsorted(os.listdir(path)) if os.path.isdir(os.path.join(path, d))]
    else:
        return []

def get_file_path(foodcoop, configuration, run, folder, ending="", notifications=None):
    if not notifications:
        notifications = []
    path = os.path.join(output_path(foodcoop, configuration), run, folder)
    if os.path.isdir(path) and ending:
        files = [os.path.join(path, f) for f in os.listdir(path) if f.endswith(ending)]
        if len(files) > 1:
            notifications.append("Warning: Multiple files found for " + run)
        if files:
            path = files[0]
    return path, notifications

def list_categories(locales, categories):
    txt = ""
    for category in categories:
        txt += "#"
        if category.number:
            txt += str(category.number)
        if category.name:
            txt += " " + category.name
        if category.subcategories:
            subcats = category.subcategories.copy()
            txt += f' ({locales["base"]["incl. subcategories"]} ' + subcats[0].name
            subcats.pop(0)
            for sc in subcats:
                txt += ", " + sc.name
            txt += ")"
        txt += "\n"
    return txt

def prepare_output(foodcoop, configuration, name=""):
    path = "data"
    os.makedirs(path, exist_ok=True)
    path = os.path.join(path, foodcoop)
    os.makedirs(path, exist_ok=True)
    path = os.path.join(path, configuration)
    os.makedirs(path, exist_ok=True)
    if name:
        path = os.path.join(path, name)
        os.makedirs(path, exist_ok=True)
    else:
        name = datetime.date.today().isoformat()
        path = os.path.join(path, name)
        number = 1
        while os.path.isdir(path + "_" + str(number)):
            number += 1
        path += "_" + str(number)
        name += "_" + str(number)
        os.makedirs(path, exist_ok=True)

    return path, name

def file_path(path, folder, file_name):
    path = os.path.join(path, folder)
    os.makedirs(path, exist_ok=True)
    return os.path.join(path, file_name)

def write_txt(file_path, content):
    with open(file_path + ".txt", "w", encoding="UTF8") as f:
        f.write(content)

def full_user_name(session):
    # Return full name of session user
    if session.foodsoft_connector:
        return " ".join([session.foodsoft_connector.first_name, session.foodsoft_connector.last_name]).strip()
    else: # TODO: check if session has automated task -> return task name (?)
        return "Unbekannt"
