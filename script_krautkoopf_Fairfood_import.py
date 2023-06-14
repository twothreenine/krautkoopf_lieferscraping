"""
Script for reading out the webshop from Fairfood Freiburg (screen-scraping) and creating a CSV file for article upload into Foodsoft.
"""

import base
import lib_Fairfood

def config_variables(): # List of the special config variables this script uses, whether they are required and how they could look like
    return [
        base.Variable(name="Foodsoft supplier ID", required=False, example=12),
        base.Variable(name="last imported run", required=False, example="2021-10-27_1"),
        base.Variable(name="read B2B shop only", required=False, example=False),
        base.Variable(name="country of destination", required=True, example="AT", description="country in which the goods will be delivered (important for VAT calculation)"),
        base.Variable(name="ignore categories by name (exact, case-sensitive)", required=False, example=["Dörr-Obst", "Brot/Gebäck"]),
        base.Variable(name="ignore categories by name (containing, case-insensitive)", required=False, example=["dörr", "bäck"]),
        base.Variable(name="ignore products by name (exact, case-sensitive)", required=False, example=["Birnennektar"]),
        base.Variable(name="ignore products by name (containing, case-insensitive)", required=False, example=["nektar"]),
        base.Variable(name="resort products in categories", required=False, example={"Kategorie 1": {"exact": False, "case-sensitive": False, "original categories": ["Obst & Gemüse", "Äpfel"], "target categories": {"Fruchtgemüse": ["Zucchini", "tomate"]}}}),
        base.Variable(name="message prefix", required=False, example="Hallo"),
        base.Variable(name="discount percentage", required=False, example=5) # TODO: not yet implemented
        ]

class ScriptRun(lib_Fairfood.ScriptRun):
    def __init__(self, foodcoop, configuration):
        super().__init__(foodcoop=foodcoop, configuration=configuration)
        self.next_possible_methods = [lib_Fairfood.read_webshop]

if __name__ == "__main__":
    run = ScriptRun(foodcoop="Test coop", configuration="Test supplier")
    while run.next_possible_methods:
        func = getattr(run, run.next_possible_methods[0].name)
        func(session) # TODO: define session
    run.save()
