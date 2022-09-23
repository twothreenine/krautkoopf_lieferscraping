# Partial draft. This script is not ready yet.

import importlib
import tabula
import pandas

import base
import foodsoft_article
import foodsoft_article_import

# Inputs this script's methods take
price_list = base.Input(name="price_list", required=True, accepted_file_types=[".pdf"], input_format="file")

# Executable script methods
run_script = base.ScriptMethod(name="run_script", inputs=[price_list])
finish = base.ScriptMethod(name="finish")

def config_variables(): # List of the special config variables this script uses, whether they are required and how they could look like
    return [
        # Not used here, but useful for detecting manual changes done in Foodsoft:
        # base.Variable(name="Foodsoft supplier ID", required=False, example=12),
        # base.Variable(name="last imported run", required=False),

        # base.Variable(name="test variable", required=False, example=43),
        # base.Variable(name="test variable 2", required=True, example=[34, 92], description="Not actually used, only for testing")
        ]

class ScriptRun(base.Run):
    def __init__(self, foodcoop, configuration):
        super().__init__(foodcoop=foodcoop, configuration=configuration)
        self.next_possible_methods = [run_script]

    def run_script(self, session, price_list):
        tables = tabula.convert_into(price_list, "renner.csv", output_format="csv", pages="all")
        # print(tables)
        # articles = []
        # test = foodsoft_article.Article(available=False, order_number=1, name="Test article", note=overlong_note, unit="1 kg", price_net=5.40, category="Test")
        # articles.append(test)
        # notifications = foodsoft_article_import.write_articles_csv(file_path=base.file_path(path=self.path, folder="download", file_name=self.configuration + "_articles_" + self.name), articles=articles)
        # base.write_txt(file_path=base.file_path(path=self.path, folder="display", file_name="Summary"), content=foodsoft_article_import.compose_articles_csv_message(supplier=self.configuration, notifications=notifications))
        # base.write_txt(file_path=base.file_path(path=self.path, folder="details", file_name="Log"), content="")
        # self.next_possible_methods = [finish]
        # self.completion_percentage = 80
        # self.log.append(base.LogEntry(action="executed", done_by=base.full_user_name(session)))

        # text file input demonstration
        # for file in test_file_input:
        #     for line in file.readlines():
        #         print(line.decode())

    def finish(self, session):
        self.next_possible_methods = []
        self.completion_percentage = 100
        self.log.append(base.LogEntry(action="finished", done_by=base.full_user_name(session)))

if __name__ == "__main__":
    importlib.invalidate_caches()
    script = importlib.import_module("script_krautkoopf_Renner_import") # I don't know why we have to do this, but if the ScriptRun object is just initialized directly (run = ScriptRun(...)), then it doesn't load when we try to load in web ("AttributeError: Can't get attribute 'ScriptRun' on <module '__main__' from 'web.py'>")
    run = script.ScriptRun(foodcoop="krautkoopf", configuration="Supplier X")
    while run.next_possible_methods:
        func = getattr(run, run.next_possible_methods[0].name)
        func()
    run.save()
