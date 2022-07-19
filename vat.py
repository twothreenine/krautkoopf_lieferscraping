"""
Screenscraping VAT rates for EU countries from an official source and putting them into objects for each country.
Use get_vat_object(country) to get an object for a specific country, for example:

>>> import vat
>>> at = vat.get_vat_object("at")
>>> at.reduced
10.0

This will return the reduced VAT rate in Austria as float. (10.0 % as of July 2022)
You can find Austria by "austria" and "AT" (both case-insensitive). Check the source table for the country names: https://europa.eu/youreurope/business/taxation/vat/vat-rules-rates/#shortcut-7
Keep in mind that there is also an alternative reduced VAT in Austria (13.0 % as of July 2022) and some other countries. Check at.alternative_reduced for that.
In case there is no such rate in the given country, a None object is returned.

If you want a direct output of a certain rate, you can use the specific functions like super_reduced(country) for that.
In case their is no such "super reduced" rate in that country, the reduced rate is returned, unless there is no reduced rate eiter, then the standard rate is returned.

>>> import vat
>>> vat.super_reduced("DE")
7.0
(which is the reduced rate, since there is no "super reduced" rate in Germany, as of July 2022)
"""

from bs4 import BeautifulSoup
import requests
import datetime


vat_objects = []

class NationalVat:
    def __init__(self, country, country_code, last_updated, last_checked, standard, reduced=None, alternative_reduced=None, super_reduced=None, parking=None):
        self.country = country
        self.country_code = country_code
        self.last_updated = last_updated
        self.last_checked = last_checked
        self.standard = standard
        self.reduced = reduced
        self.alternative_reduced = alternative_reduced
        self.super_reduced = super_reduced
        self.parking = parking

def read_rate_column(text):
    if "-" in text:
        return None
    else:
        return float(text.strip()) # float(text) ?

def create_vat_objects():
    global vat_objects
    new_vat_objects = []
    page = BeautifulSoup(requests.get("https://europa.eu/youreurope/business/taxation/vat/vat-rules-rates/").text, features="html.parser").body
    tables = page.find_all('table')
    vat_table = None
    table_valid = None
    last_updated = None
    last_checked = datetime.date.today()
    for t in tables:
        if "List of VAT rates" in t.text:
            vat_table = t
    if vat_table:
        for row in vat_table.tbody.find_all('tr'):
            columns = row.find_all('td')
            first_column = columns[0].text
            if "List of VAT rates" in first_column:
                last_updated = datetime.datetime.strptime(first_column.split("last updated as of ")[1].split(")")[0], "%d %B %Y").date()
                continue
            if "Member State" in first_column:
                if "Country code" in columns[1].text and "Standard rate" in columns[2].text and "Reduced rate" in columns[3].text and "Super reduced rate" in columns[4].text and "Parking rate" in columns[5].text:
                    table_valid = True
                    continue
                else:
                    table_valid = False
                    break
            if table_valid:
                reduced_rates = columns[3].text.split(" / ")
                reduced_rate = None
                alternative_reduced_rate = None
                if reduced_rates:
                    reduced_rate = read_rate_column(reduced_rates[0])
                    if len(reduced_rates) > 1:
                        alternative_reduced_rate = read_rate_column(reduced_rates[1])

                vat_object = NationalVat(country=columns[0].text.strip(), country_code=columns[1].text.strip(), last_updated=last_updated, last_checked=last_checked, standard=read_rate_column(columns[2].text), reduced=reduced_rate, alternative_reduced=alternative_reduced_rate, super_reduced=read_rate_column(columns[4].text), parking=read_rate_column(columns[5].text))
                new_vat_objects.append(vat_object)
            else:
                print("EU VAT Table has changed, please update vat screenscraping (vat.py)")
        if new_vat_objects:
            vat_objects = new_vat_objects.copy()

def check_for_vat_objects():
    if not vat_objects:
        create_vat_objects()
    if vat_objects:
        if vat_objects[0].last_checked != datetime.date.today():
            create_vat_objects()

def find_matching_country(country):
    matches = [vo for vo in vat_objects if vo.country.casefold() == country.casefold() or vo.country_code.casefold() == country.casefold()]
    if matches:
        if len(matches) == 1:
            return matches[0]
        else:
            print(f"Error: {str(len(matches))} found for this country!")
    else:
        print("Error: No matches found for this country!")

def get_vat_object(country):
    check_for_vat_objects()
    return find_matching_country(country)

def standard(country):
    check_for_vat_objects()
    vo = find_matching_country(country)
    if vo:
        return vo.standard

def reduced(country):
    check_for_vat_objects()
    vo = find_matching_country(country)
    if vo:
        if vo.reduced:
            return vo.reduced
        else:
            return vo.standard

def alternative_reduced(country):
    check_for_vat_objects()
    vo = find_matching_country(country)
    if vo:
        if vo.alternative_reduced:
            return vo.alternative_reduced
        else:
            return reduced(country)

def super_reduced(country):
    check_for_vat_objects()
    vo = find_matching_country(country)
    if vo:
        if vo.super_reduced:
            return vo.super_reduced
        else:
            return reduced(country)

def parking(country):
    check_for_vat_objects()
    vo = find_matching_country(country)
    if vo:
        if vo.parking:
            return vo.parking
        else:
            return vo.standard

def print_vat_table():
    for vo in vat_objects:
        print(f"{vo.country} ({vo.country_code}):\n \
            Standard rate: {vo.standard} %\n \
            Reduced rate: {vo.reduced} %\n \
            Alternative reduced rate: {vo.alternative_reduced} %\n \
            Super reduced rate: {vo.super_reduced} %\n \
            Parking rate: {vo.parking} %\n \
            last updated: {vo.last_updated}\n \
            last checked: {vo.last_checked}")

if __name__ == "__main__":
    create_vat_objects()
    print_vat_table()
