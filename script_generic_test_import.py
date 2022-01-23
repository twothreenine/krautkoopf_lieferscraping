import importlib
import csv

import base
import foodsoft_article
import foodsoft_article_import

# Inputs this script's methods take
test_input = base.Input(name="test_input", required=False, example="bla bla")
test_file_input = base.Input(name="test_file_input", required=False, accepted_file_types=[".csv"], input_format="files")

# Executable script methods
run_script = base.ScriptMethod(name="run_script", inputs=[test_input, test_file_input])
finish = base.ScriptMethod(name="finish")

def config_variables(): # List of the special config variables this script uses, whether they are required and how they could look like
    return [
        # Not used here, but useful for detecting manual changes done in Foodsoft:
        # base.Variable(name="Foodsoft supplier ID", required=False, example=12),
        # base.Variable(name="last imported run", required=False),
        base.Variable(name="test variable", required=False, example=43),
        base.Variable(name="test variable 2", required=True, example=[34, 92], description="Not actually used, only for testing")
        ]

def environment_variables(): # List of the special environment variables this script uses, whether they are required and how they could look like
    return [
        # base.Variable(name="LS_FOODSOFT_URL", required=False, example="https://app.foodcoops.at/coop_xy/"),
        # base.Variable(name="LS_FOODSOFT_USER", required=False, example="name@foobar.com"),
        # base.Variable(name="LS_FOODSOFT_PASS", required=False, example="asdf1234")
        ]

class ScriptRun(base.Run):
    def __init__(self, foodcoop, configuration):
        super().__init__(foodcoop=foodcoop, configuration=configuration)
        self.next_possible_methods = [run_script]

    def run_script(self, test_input="", test_file_input=None):
        articles = []
        overlong_note = "This is a very long text. Since Foodsoft only supports up to 255 characters in the articles' data strings (note, manufacturer, origin) and won't validate them by itself, we have to resize it in order to not cause an error. Nobody would read it anyway to the end!"
        test = foodsoft_article.Article(available=False, order_number=1, name="Test article", note=overlong_note, unit="1 kg", price_net=5.40, category="Test")
        articles.append(test)

        # csv file input test
        # TODO: doesn't work, since the file is open in binary mode
        # for file in test_file_input:
        #     articles_from_csv = list(csv.reader(file, delimiter=';'))
        #     print(articles_from_csv)

        #     if len(articles_from_csv) > 1:
        #         for row in articles_from_csv[1:]:
        #             article = Article(order_number=row[1], name=row[2], note=row[3], manufacturer=row[4], origin=row[5], unit=row[6], price_net=row[7], vat=row[8], deposit=row[9], unit_quantity=row[10], category=row[13])
        #             articles.append(article)

        notifications = foodsoft_article_import.write_articles_csv(file_path=base.file_path(path=self.path, folder="download", file_name=self.configuration + "_articles_" + self.name), articles=articles)
        test = foodsoft_article_import.write_articles_csv(file_path=base.file_path(path=self.path, folder="download", file_name=self.configuration + "_test_" + self.name), articles=articles)
        base.write_txt(file_path=base.file_path(path=self.path, folder="display", file_name="Summary"), content=foodsoft_article_import.compose_articles_csv_message(supplier=self.configuration, notifications=notifications))
        base.write_txt(file_path=base.file_path(path=self.path, folder="details", file_name="Log"), content="")
        self.next_possible_methods = [finish]
        self.completion_percentage = 80

        # input demonstration
        if test_input:
            executed_entry = base.LogEntry(action="executed", done_by=test_input)
            self.log.append(executed_entry)

        # text file input demonstration
        # for file in test_file_input:
        #     for line in file.readlines():
        #         print(line.decode())

    def finish(self):
        self.next_possible_methods = []
        self.completion_percentage = 100

if __name__ == "__main__":
    importlib.invalidate_caches()
    script = importlib.import_module("script_generic_test_import") # I don't know why we have to do this, but if the ScriptRun object is just initialized directly (run = ScriptRun(...)), then it doesn't load when we try to load in web ("AttributeError: Can't get attribute 'ScriptRun' on <module '__main__' from 'web.py'>")
    run = script.ScriptRun(foodcoop="krautkoopf", configuration="Supplier X")
    while run.next_possible_methods:
        func = getattr(run, run.next_possible_methods[0].name)
        func()
    run.save()