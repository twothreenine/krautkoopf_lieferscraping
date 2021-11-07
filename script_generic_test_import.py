import base

# Inputs this script's methods take
test_input = base.Input(name="Test input", required=False, example="bla bla")
test_file_input = base.Input(name="Test file input", required=False, accepted_file_types=["txt"])

# Executable script methods
run_script = base.ScriptMethod(name="run_script", inputs=[test_input, test_file_input])
finish = base.ScriptMethod(name="finish")

def config_variables(): # List of the special config variables this script uses, whether they are required and how they could look like
    return [
        base.Variable(name="Test-Variable", required=False, example=43),
        base.Variable(name="Test-Variable 2", required=True, example=[34, 92], description="Not actually used, only for testing")
        ]

def environment_variables(): # List of the special environment variables this script uses, whether they are required and how they could look like
    return [
        # base.Variable(name="LS_FOODSOFT_URL", required=False, example="https://app.foodcoops.at/coop_xy/"),
        # base.Variable(name="LS_FOODSOFT_URL", required=False, example="name@foobar.com"),
        # base.Variable(name="LS_FOODSOFT_PASS", required=False, example="asdf1234")
        ]

class ScriptRun(base.Run):
    def __init__(self, foodcoop, configuration):
        super().__init__(foodcoop=foodcoop, configuration=configuration)
        self.next_possible_methods = [run_script]

    def run_script(self):
        articles = []
        overlong_note = "This is a very long text. Since Foodsoft only supports up to 255 characters in the articles' data strings (note, manufacturer, origin) and won't validate them by itself, we have to resize it in order to not cause an error. Nobody would read it anyway to the end!"
        test = base.Article(available=False, order_number=1, name="Test article", note=overlong_note, unit="1 kg", price_net=5.40, category="Test")
        articles.append(test)

        notifications = base.write_articles_csv(file_path=base.file_path(path=self.path, folder="download", file_name=self.configuration + "_articles_" + self.name), articles=articles)
        test = base.write_articles_csv(file_path=base.file_path(path=self.path, folder="download", file_name=self.configuration + "_test_" + self.name), articles=articles)
        base.write_txt(file_path=base.file_path(path=self.path, folder="display", file_name="Summary"), content=base.compose_articles_csv_message(supplier=self.configuration, notifications=notifications))
        base.write_txt(file_path=base.file_path(path=self.path, folder="details", file_name="Log"), content="")
        self.next_possible_methods = [finish]
        self.completion_percentage = 80

    def finish(self):
        self.next_possible_methods = []
        self.completion_percentage = 100

if __name__ == "__main__":
    run = ScriptRun(foodcoop="Test coop", configuration="Test supplier")
    while run.next_possible_methods:
        func = getattr(run, run.next_possible_methods[0].name)
        func()
    run.save()