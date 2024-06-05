"""
Screenscraping VAT rates for EU countries from an official source and putting them into objects for each country.
Use get_vat_object(country) to get an object for a specific country, for example:

>>> import vat
>>> vat_collection = vat.VatCollection()
>>> at_vat_object = vat_collection.find_matching_country('AT')
>>> at_vat_object.get_reduced()
10.0

This will return the reduced VAT rate in Austria as float. (10.0 % as of July 2022)
Keep in mind that there is also an alternative reduced VAT in Austria (13.0 % as of July 2022) and some other countries.
Check at_vat_object.get_alternative_reduced() for that.

You can find Austria by "austria" and "AT" (both case-insensitive).
Check the source table for the country names: https://europa.eu/youreurope/business/taxation/vat/vat-rules-rates/#shortcut-7

Note the difference between:
>>> <vat_object>.alternative_reduced
>>> <vat_object>.get_alternative_reduced()
<vat_object>.<rate> will return None if there is no such rate in that country.
<vat_object>.get_<rate>() will always return something -- if there is no alternative_reduced rate in the given country, 
the reduced rate will be returned (or else, the standard rate.)

Example:

>>> import vat
>>> vat_collection = vat.VatCollection()
>>> de_vat_object = vat_collection.find_matching_country('DE')
>>> de_vat_object.get_super_reduced()
7.0
(which is the reduced rate, since there is no "super reduced" rate in Germany, as of July 2022)
"""

from bs4 import BeautifulSoup
import requests
import datetime

class VatCollection:
    def __init__(self):
        self.vat_objects = []
        self.read_vats()

    def __str__(self):
        string = "last checked: {vo.last_checked}\n\n"
        for vo in self.vat_objects:
            string += f"{vo.country} ({vo.country_code}):\n \
                        Standard rate: {vo.standard} %\n \
                        Reduced rate: {vo.reduced} %\n \
                        Alternative reduced rate: {vo.alternative_reduced} %\n \
                        Super reduced rate: {vo.super_reduced} %\n \
                        Parking rate: {vo.parking} %\n \
                        last updated: {vo.last_updated}\n\n"
        return string

    def update(self):
        if self.last_checked != datetime.date.today():
            self.read_vats()

    def read_vats(self):
        new_vat_objects = []
        page = BeautifulSoup(requests.get("https://europa.eu/youreurope/business/taxation/vat/vat-rules-rates/").text, features="html.parser").body
        tables = page.find_all('table')
        vat_collection = None
        table_valid = None
        last_updated = None
        for t in tables:
            if first_row := t.find('tr').find('td'):
                if "List of VAT rates" in first_row.text:
                    vat_collection = t
        if vat_collection:
            rows = vat_collection.tbody.find_all('tr')
            column_headers = rows[1].find_all('td')
            if "Country code" in column_headers[0].text and "Member State" in column_headers[1].text and "Standard rate" in column_headers[2].text and "Reduced rate" in column_headers[3].text and "Super reduced rate" in column_headers[4].text and "Parking rate" in column_headers[5].text:
                table_valid = True
                for row in rows[2:]:
                    columns = row.find_all('td')
                    reduced_rates = columns[3].text.split(" / ")
                    reduced_rate = None
                    alternative_reduced_rate = None
                    if reduced_rates:
                        reduced_rate = read_rate_column(reduced_rates[0])
                        if len(reduced_rates) > 1:
                            alternative_reduced_rate = read_rate_column(reduced_rates[1])

                    new_vat_objects.append(NationalVat(country=columns[1].text.strip(), country_code=columns[0].text.strip(), last_updated=last_updated, standard=read_rate_column(columns[2].text), reduced=reduced_rate, alternative_reduced=alternative_reduced_rate, super_reduced=read_rate_column(columns[4].text), parking=read_rate_column(columns[5].text)))
                self.vat_objects = new_vat_objects
                self.last_checked = datetime.date.today()
        if not table_valid:
            print("EU VAT Table has changed, please update vat screenscraping (vat.py)")

    def find_matching_country(self, country):
        return next(vo for vo in self.vat_objects if vo.country.casefold() == country.casefold() or vo.country_code.casefold() == country.casefold())

    def get_vat_object(self, country):
        self.update()
        return self.find_matching_country(country)

class NationalVat:
    def __init__(self, country, country_code, last_updated, standard, reduced=None, alternative_reduced=None, super_reduced=None, parking=None):
        self.country = country
        self.country_code = country_code
        self.last_updated = last_updated
        self.standard = standard
        self.reduced = reduced
        self.alternative_reduced = alternative_reduced
        self.super_reduced = super_reduced
        self.parking = parking

    def get_standard(self):
        return self.standard

    def get_reduced(self):
        if self.reduced:
            return self.reduced
        else:
            return self.standard

    def get_alternative_reduced(self):
        if self.alternative_reduced:
            return self.alternative_reduced
        else:
            return self.get_reduced()

    def get_super_reduced(self):
        if self.super_reduced:
            return self.super_reduced
        else:
            return self.get_reduced()

    def get_parking(self):
        if self.parking:
            return self.parking
        else:
            return self.standard

def read_rate_column(text):
    if "-" in text:
        return None
    else:
        return float(text.strip()) # float(text) ?

if __name__ == "__main__":
    vc = VatCollection()
    print(vc)
