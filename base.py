import csv
import os
import logging
import json
import datetime
import dill

class Run:
    """
    An instance of a script execution.
    """
    def __init__(self, foodcoop, configuration, started_by, name="", next_possible_methods=[]):
        self.path, self.name = prepare_output(foodcoop=foodcoop, configuration=configuration, name=name)
        self.foodcoop = foodcoop
        self.configuration = configuration
        self.started_by = started_by
        self.next_possible_methods = next_possible_methods
        self.completion_percentage = 0

    def save(self):
        file_path = os.path.join(self.path, "run.obj")
        with open(file_path, 'wb') as file:
            dill.dump(self, file)

    @classmethod
    def load(cls, path):
        with open(os.path.join(path, "run.obj"), 'rb') as file:
            return dill.load(file)

class ScriptMethod:
    """
    A callable method/function in a script.
    Create ScriptMethod instances for all methods which should be callable by the user at some point,
    and put them into next_possible_methods at the end of a method after which they should be callable.
    """
    def __init__(self, name, inputs=[]):
        self.name = name
        self.inputs = inputs

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
    def __init__(self, name, required=False, accepted_file_types=[], example=None, description=""):
        self.name = name
        self.required = required
        self.accepted_file_types = accepted_file_types # for example ["csv"], or [] if not a file
        self.example = example # important (if not a file) to know which type of input should be asked for
        self.description = description

class Category:
    """
    Nestable categories e.g. for articles, for usage within a script.
    """
    def __init__(self, number, name="", subcategories=[]):
        self.number = number
        self.name = name
        self.subcategories = subcategories

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

def read_config(foodcoop, configuration="", ensure_subconfig=""):
    os.makedirs("config", exist_ok=True)
    filename = "config/" + foodcoop + ".json"
    if os.path.isfile(filename):
        with open(filename) as json_file:
            config = json.load(json_file)
    else:
        config = {}
    if configuration:
        if configuration not in config:
            configuration_config = {}
        else:
            configuration_config = config[configuration]
        if ensure_subconfig:
            if ensure_subconfig not in configuration_config:
                configuration_config[ensure_subconfig] = {}
        return configuration_config
    else:
        return config

def read_in_config(config, detail, alternative=None):
    if detail in config:
        return config[detail]
    else:
        return alternative

def save_config(foodcoop, config):
    os.makedirs("config", exist_ok=True)
    filename = "config/" + foodcoop + ".json"
    with open(filename, "w") as json_file:
        json.dump(config, json_file, indent=4)

def save_configuration(foodcoop, configuration, new_config):
    config = read_config(foodcoop)
    if configuration not in config:
        config[configuration] = {}
    config[configuration] = new_config
    save_config(foodcoop, config)

def set_configuration_detail(foodcoop, configuration, detail, value):
    config = read_config(foodcoop)
    if configuration not in config:
        config[configuration] = {}
    config[configuration][detail] = value
    save_config(foodcoop, config)

def rename_configuration(foodcoop, old_configuration_name, new_configuration_name):
    config = read_config(foodcoop)
    if old_configuration_name in config:
        config[new_configuration_name] = config.pop(old_configuration_name)
        save_config(foodcoop, config)
        existing_output_path = output_path(foodcoop, old_configuration_name)
        new_output_path = output_path(foodcoop, new_configuration_name)
        if os.path.exists(new_output_path):
            for entry in os.scandir(existing_output_path):
                new_entry_name = entry.name
                while os.path.exists(os.path.join(new_output_path, new_entry_name)):
                    new_entry_name += "*"
                os.rename(os.path.join(existing_output_path, entry.name), os.path.join(new_output_path, new_entry_name))
            os.rmdir(existing_output_path)
        else:
            os.rename(existing_output_path, new_output_path)
        return new_configuration_name
    else:
        return None

def delete_configuration(foodcoop, configuration):
    config = read_config(foodcoop)
    deleted_configuration = config.pop(configuration, None)
    save_config(foodcoop, config)
    updated_config = read_config(foodcoop)
    if deleted_configuration:
        if deleted_configuration in updated_config.items():
            deleted_configuration = None
    return deleted_configuration

def output_path(foodcoop, configuration):
    return os.path.join("output", foodcoop, configuration)

def get_outputs(foodcoop, configuration):
    path = output_path(foodcoop, configuration)
    if os.path.exists(path):
        return [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
    else:
        return []

def get_file_path(foodcoop, configuration, run, folder, ending=""):
    path = os.path.join(output_path(foodcoop, configuration), run, folder)
    files = [os.path.join(path, f) for f in os.listdir(path) if f.endswith(ending)]
    if len(files) > 1:
        print("Warning: Multiple files found for " + run)
    if files:
        return files[0]

def list_categories(categories):
    txt = ""
    for category in categories:
        txt += "#" + str(category.number) + " " + category.name
        if category.subcategories:
            subcats = category.subcategories.copy()
            txt += " (inkl. Unterkategorien " + subcats[0].name
            subcats.pop(0)
            for sc in subcats:
                txt += ", " + sc.name
            txt += ")"
        txt += "\n"
    return txt

def prepare_output(foodcoop, configuration, name=""):
    path = "output"
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