import base

def run(foodcoop, configuration):
    articles = []
    overlong_note = "This is a very long text. Since Foodsoft only supports up to 255 characters in the articles' data strings (note, manufacturer, origin) and won't validate them by itself, we have to resize it in order to not cause an error. Nobody would read it anyway to the end!"
    test = base.Article(available=False, order_number=1, name="Test article", note=overlong_note, unit="1 kg", price_net=5.40, category="Test")
    articles.append(test)

    path, date = base.prepare_output(foodcoop=foodcoop, configuration=configuration)
    notifications = base.write_articles_csv(file_path=base.file_path(path=path, folder="download", file_name=configuration + "_articles_" + date), articles=articles)
    test = base.write_articles_csv(file_path=base.file_path(path=path, folder="download", file_name=configuration + "_test_" + date), articles=articles)
    base.write_txt(file_path=base.file_path(path=path, folder="display", file_name="Summary"), content=base.compose_articles_csv_message(supplier=configuration, notifications=notifications))
    base.write_txt(file_path=base.file_path(path=path, folder="details", file_name="Log"), content="")

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

def inputs(): # List of the inputs this script takes, whether they are required, what type of input, how it could look like etc.
    return [
        base.Input(name="Test input", required=False, example="bla bla"),
        base.Input(name="Test file input", required=False, accepted_file_types=["txt"])
        ]

if __name__ == "__main__":
    run(foodcoop="Test coop", configuration="Test supplier")