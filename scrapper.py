from lxml import html
from exceptions import ValueError

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException

import zillow
import requests
import urllib3
import googlemaps
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


def print_err (err_desc, browser):
	print "Error! {0}".format (err_desc)

	if browser:
		browser.close ()

	exit ()


def load_credentials ():
	with open ('zws_key', 'r') as zws_file:
		zws_id = zws_file.read ().replace ('\n', '')

	if not zws_id:
		print_err ("Cannot find Zillow API key", None)

	with open ('gapi_key', 'r') as gapi_file:
		google_id = gapi_file.read ().replace ('\n', '')

	if not google_id:
		print_err ("Cannot find Google API key", None)

	return zws_id, google_id


def get_extended_info (zapi, gmaps, zws_id, zpid):
	zestimate = None 
	tax_assessment = None 
	year = None 
	n_nearby_hospitals = None 
	n_nearby_uni = None
	latitude = None
	longitude = None


	zestimate_dict = zapi.GetZEstimate (zws_id, zpid).get_dict ()


	if "zestimate" in zestimate_dict:
		if "amount" in zestimate_dict["zestimate"]:
			zestimate = zestimate_dict['zestimate']['amount']

	if "extended_data" in zestimate_dict:
		if "tax_assessment" in zestimate_dict["extended_data"]:
			tax_assessment = zestimate_dict['extended_data']['tax_assessment']

		if "year_built" in zestimate_dict["extended_data"]:
			year = zestimate_dict['extended_data']['year_built']

	if "full_address" in zestimate_dict:
		if "latitude" in zestimate_dict["full_address"]:
			latitude = zestimate_dict['full_address']['latitude']

		if "longitude" in zestimate_dict["full_address"]:
			longitude = zestimate_dict['full_address']['longitude']

	if longitude and latitude:
		nearby_hospitals = gmaps.places_nearby (type="hospital", location=(latitude, longitude), radius=1000)
		nearby_uni = gmaps.places_nearby (type="university", location=(latitude, longitude), radius=1000)

		n_nearby_hospitals = len (nearby_hospitals['results'])
		n_nearby_uni = len (nearby_uni['results'])

	return zestimate, tax_assessment, year, n_nearby_hospitals, n_nearby_uni


def get_rental_info (browser, url):
	rental = None
	year = None

	browser.get (url)
	button = browser.find_elements_by_xpath ("//section[@id='homeValue']")

	if button:
		button[0].click ()

		button = browser.find_element_by_link_text ("See more home value estimates")

		if button:
			button.click ()

			parser = html.fromstring (browser.page_source)
			rental = parser.xpath (".//h4[@class='zestimate-value ds-standard-label']//text()")
			rental = re.sub ('[^0-9]','', rental)
			year = parser.xpath (".//span[@class='ds-body ds-home-fact-value']//text()")[1]
	else:
		button = browser.find_elements_by_xpath ("//div[@class='toggle-section']")

		if button:
			button[0].click()

			parser = html.fromstring (browser.page_source)
			rental = parser.xpath (".//div[@class='zestimate-value']//text()")[1]
			rental = re.sub('[^0-9]','', rental)
			year = parser.xpath (".//div[@class='fact-value']//text()")[1]

	return rental, year


def process_results (results):
	for result in results:
		price = int (result["price"]) if result["price"] else None
		zestimate = int (result["zestimate"]) if result["zestimate"] else None
		rental = int (result["rental"]) if result["rental"] else None
		n_hospitals = int (result["n_nearby_hospitals"]) if result["n_nearby_hospitals"] else None
		n_uni = int (result["n_nearby_uni"]) if result["n_nearby_uni"] else None

		output = {}

		if price and zestimate:
			value_ratio = price * 1.0 / zestimate * 100

			if value_ratio < 50:
				output["Value"] = value_ratio

				if n_hospitals > 0:
					output["Hospital"] = n_hospitals

				if n_uni > 0:
					output["University"] = n_uni
		
		if rental and price: 
			rental_ratio = rental * 1.0 / price * 100

			if rental_ratio > 1.5:
				output["Rents"] = rental_ratio

				if n_hospitals > 0:
					output["Hospital"] = n_hospitals

				if n_uni > 0:
					output["University"] = n_uni

		if output:
			print "-------------------------------------------------------------------------"
			print result["url"]
			print output
			print "-------------------------------------------------------------------------"

def zillow_scrape (city, state, max_price, min_n_beds):
	page_num = 1
	properties_list = []

	zws_id, google_id = load_credentials ()

	zapi = zillow.ValuationApi ()
	gmaps = googlemaps.Client (key=google_id)
	browser = webdriver.Chrome ()

	while 1:
		try:
			url = "https://www.zillow.com/homes/for_sale/{0}-{1}/house_type/{2}-_beds/0-{3}_price/{4}_p".format(city, state, min_n_beds, max_price, page_num)
			response = requests.get (url, headers=headers, verify=False)
			parser = html.fromstring (response.text)
			search_results = parser.xpath ("//div[@id='search-results']//article")
			i_prop = 0

			if not search_results:
				print "No results found!"
				browser.close ()

				return properties_list

			for result in search_results:
				data = {}
				i_prop += 1

				raw_address = result.xpath (".//span[@itemprop='address']//span[@itemprop='streetAddress']//text()")
				raw_city = result.xpath (".//span[@itemprop='address']//span[@itemprop='addressLocality']//text()")
				raw_state = result.xpath (".//span[@itemprop='address']//span[@itemprop='addressRegion']//text()")
				raw_postal_code = result.xpath (".//span[@itemprop='address']//span[@itemprop='postalCode']//text()")
				raw_price = result.xpath (".//span[@class='zsg-photo-card-price']//text()")
				raw_info = result.xpath (".//span[@class='zsg-photo-card-info']//text()")
				raw_url = result.xpath (".//a[contains(@class,'overlay-link')]/@href")
				raw_zpid = result.xpath (".//a[contains(@title, 'Save this home')]//@data-fm-zpid")
				raw_title = result.xpath (".//h4//text()")
				
				if not raw_price:
					continue

				
				url = "https://www.zillow.com" + raw_url[0] if raw_url else None
				zpid = ''.join (raw_zpid).strip () if raw_zpid else None


				zestimate = None
				tax_assessment = None
				ex_year = None
				n_nearby_hospitals = None
				n_nearby_uni = None

				try:
					if zpid:	
						zestimate, tax_assessment, ex_year, n_nearby_hospitals, n_nearby_uni = get_extended_info (
							zapi, gmaps, zws_id, zpid)
				except:
					pass

				year = ex_year
				rental = None

				# if url:
				# 	rental, year = get_rental_info (browser, url)
					
				# 	if not year:
				# 		year = ex_year

				data["address"] = ' '.join (' '.join(raw_address).split ()) if raw_address else None
				data["city"] = ''.join (raw_city).strip () if raw_city else None
				data["state"] = ''.join (raw_state).strip () if raw_state else None
				data["postal_code"] = ''.join (raw_postal_code).strip () if raw_postal_code else None
				data["price"] = re.sub('[^0-9]','', ''.join (raw_price).strip () if raw_price else None)
				data["info"] = ' '.join (' '.join (raw_info).split ()).replace (u"\xb7",',')
				data["title"] = ''.join (raw_title) if raw_title else None
				data["url"] = url
				data["zestimate"] = zestimate
				data["tax_assessment"] = tax_assessment
				data["year"] = year
				data["n_nearby_hospitals"] = n_nearby_hospitals
				data["n_nearby_uni"] = n_nearby_uni
				data["rental"] = rental

				if not any (prop["url"] == 'url' for prop in properties_list):
					properties_list.append (data)

			if i_prop < 25:
				break

			page_num += 1

		except Exception, e:
			print_err ("Exception: {0}".format(e), browser)

	browser.close ()

	return properties_list


results = zillow_scrape ("Chicago", "IL", 50000, 2)

process_results (results)
