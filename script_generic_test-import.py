import base

def run(foodcoop, supplier):
    articles = []
    overlong_note = "This is a very long text. Since Foodsoft only supports up to 255 characters in the articles' data strings (note, manufacturer, origin) and won't validate them by itself, we have to resize it in order to not cause an error. Nobody would read it anyway to the end!"
    test = base.Article(available=False, order_number=1, name="Test article", note=overlong_note, unit="1 kg", price_net=5.40, category="Test")
    articles.append(test)

    base.write_csv(foodcoop=foodcoop, supplier=supplier, articles=articles)
    return "Test import completed!"

def config_variables(): # Lists the special config variables this script uses and for each of them: whether they are required, example
    return {"Test": {"required": False, "example": 43},
            "Test2": {"required": True, "example": [34, 92]}}

def info(): # Info whether the script requests (takes) a file and whether it returns (generates) a file
    requests_file = False
    returns_file = True
    return requests_file, returns_file

if __name__ == "__main__":
    message = run(foodcoop="Test coop", supplier="Test supplier")
    print(message)