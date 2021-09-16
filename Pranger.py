from bs4 import BeautifulSoup
import requests

def getCategory(id) :
  response = requests.get("https://oekobox-online.eu/v3/shop/pranger/s2/C6.0.219C/category.jsp?categoryid="+str(id)+"&cartredir=1")

  html_string = response.text
  parsed_html = BeautifulSoup(html_string,features="html.parser")

  table = parsed_html.body.find_all('table')
  name  = parsed_html.body.find(class_="font2 ic2")

  return {"name" : name, "items" : table}

def printIfFound(src, class_name, prefix) :
  item = src.find(class_=class_name)
  if item and item.get_text().strip() != "" : 
    print(prefix + ": " + item.get_text().strip())

for idx in range(20) :
  cat = getCategory(idx)
  if cat["items"] == [] : 
    continue

  print(cat["name"].get_text().strip())

  for item in cat["items"] :
    print("  " + item.find(class_="font2 ic3 itemname").text)
    printIfFound(item, "ic2 producer", "    Hersteller")
    printIfFound(item, "ic2 cinfotxt", "    Info")
    print("    Kaufoptionen:")
    price = item.find(class_="font2 ic2 baseprice")
    
    for option in price.find_all("option") + price.find_all(class_="oo-item-price") :
      print("      " + option.get_text().strip())

  idx = idx+1