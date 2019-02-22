from lxml import html

from utilities import print_time, print_err, is_digit
from property_info import property_analyzer
from property_analysis import process_results

import requests
import urllib3
import re


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


headers = {
					'accept':'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
					'accept-encoding':'gzip, deflate, br',
					'accept-language':'en-US,en;q=0.9,ar;q=0.8',
					'cache-control':'max-age=0',
					'upgrade-insecure-requests':'1',
					'user-agent':'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36'
		}


def zillow_scrape (city, state, max_price, min_n_beds):
	page_num = 1
	properties_list = []

	prop_analyzer = property_analyzer ()

	print "Downloading properties from Zillow",

	while 1:
		try:
			url = "https://www.zillow.com/homes/for_sale/{0}-{1}/house_type/{2}-_beds/0-{3}_price/{4}_p".format(
				city, state, min_n_beds, max_price, page_num)
			response = requests.get (url, headers=headers, verify=False)
			parser = html.fromstring (response.text)
			search_results = parser.xpath ("//div[@id='search-results']//article")
			i_prop = 0

			if not search_results:
				prop_analyzer.deinit ()
				return properties_list

			for result in search_results:
				data = {}
				i_prop += 1
				print ".",

				raw_address = result.xpath (".//span[@itemprop='address']//span[@itemprop='streetAddress']//text()")
				raw_price = result.xpath (".//span[@class='zsg-photo-card-price']//text()")
				raw_info = result.xpath (".//span[@class='zsg-photo-card-info']//text()")
				raw_url = result.xpath (".//a[contains(@class,'overlay-link')]/@href")
				raw_zpid = result.xpath (".//a[contains(@title, 'Save this home')]//@data-fm-zpid")
				raw_postal_code = result.xpath(".//span[@itemprop='address']//span[@itemprop='postalCode']//text()")

				address = " ".join (" ".join(raw_address).split ()) if raw_address else None
				s_price = "".join (raw_price).strip ().lower() if raw_price else None
				info = " ".join (" ".join (raw_info).split ()).replace (u"\xb7", ",") if raw_info else None
				prop_url = "https://www.zillow.com" + raw_url[0] if raw_url else None
				zpid = "".join (raw_zpid).strip () if raw_zpid else None
				postal_code = "".join (raw_postal_code).strip () if raw_zpid else None

				if not s_price:
					continue

				price = int (re.sub("[^0-9]","", s_price))
				
				if "k" in s_price:
					price *= 1000
				
				zestimate, tax, year, geocode = prop_analyzer.get_zestimate_info (zpid)
				nearby_hospitals, nearby_uni = prop_analyzer.get_nearby_info (geocode, 1)
				# rental, year = prop_analyzer.get_zillow_rental_info (prop_url)
				
				bd = None
				ba = None
				sqft = None

				if info:
					info = [float (s) for s in info.replace (",", "").split () if is_digit (s)]
					
					if len (info) == 3:
						bd = info[0]
						ba = info[1]
						sqft = info[2]

				rental = prop_analyzer.get_rental_comps_craigslist (address, city, postal_code, 3, bd, ba, sqft)

				data["address"] = address
				data["price"] = price
				data["info"] = info
				data["url"] = prop_url
				data["zestimate"] = zestimate
				data["tax"] = tax
				data["year"] = year
				data["nearby_hospitals"] = nearby_hospitals
				data["nearby_uni"] = nearby_uni
				data["rental"] = rental

				if not any (prop["url"] == prop_url for prop in properties_list):
					properties_list.append (data)

			if i_prop < 25:
				break

			page_num += 1

		except Exception, e:
			prop_analyzer.deinit ()
			print_err ("Exception: {0}".format(e))

	prop_analyzer.deinit ()

	return properties_list

results = zillow_scrape ("Houston", "TX", 100000, 2)

print ""
print "Found {0} potential properties".format (len (results))

process_results (results)