from base import *

supplier = "Test supplier"
articles = []
overlong_note = "This is a very long text. Since Foodsoft only supports up to 255 characters in the articles' data strings (order number, name, note, manufacturer, origin, unit) and won't validate them by itself, we have to resize it in order to not cause an error. Nobody would read it anyway to the end!"
test = Article(available=False, order_number=1, name="Test article", note=overlong_note, unit="1 kg", price_net=5.40, category="Test")
articles.append(test)

write_csv(supplier=supplier, articles=articles)