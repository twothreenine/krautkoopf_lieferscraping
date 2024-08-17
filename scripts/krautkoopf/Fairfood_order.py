"""
Script for placing orders in the webshop of Fairfood Freiburg (screen-scraping) based on a Foodsoft order.
"""

import base
import script_libs.krautkoopf.Fairfood as lib_Fairfood

def config_variables(): # List of the special config variables this script uses, whether they are required and how they could look like
    return [
        base.Variable(name="Foodsoft supplier ID", required=False, example=12),
        base.Variable(name="message prefix", required=False, example="Hallo")
        ]

class ScriptRun(lib_Fairfood.ScriptRun):
    def __init__(self, foodcoop, configuration):
        super().__init__(foodcoop=foodcoop, configuration=configuration)
        self.next_possible_methods = [lib_Fairfood.order]
