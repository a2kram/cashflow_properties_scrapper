from lxml import html
from exceptions import ValueError

import zillow
import requests
import unicodecsv as csv
import urllib3
import argparse
import googlemaps
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

zws_id = None
google_id = None

headers = {
					'accept':'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
					'accept-encoding':'gzip, deflate, br',
					'accept-language':'en-US,en;q=0.9,ar;q=0.8',
					'cache-control':'max-age=0',
					'upgrade-insecure-requests':'1',
					'user-agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3626.96 Safari/537.36'
		}

def parse (city, state, max_price=100000, min_n_beds=2):
	page_num = 1
	properties_list = []

	api = zillow.ValuationApi ()
	gmaps = googlemaps.Client (key=google_id)

	while 1:
		try:
			url = "https://www.zillow.com/homes/for_sale/{0}-{1}/house_type/{2}-_beds/0-{3}_price/{4}_p".format(city, state, min_n_beds, max_price, page_num)
			response = requests.get (url, headers=headers, verify=False)
			parser = html.fromstring (response.text)
			search_results = parser.xpath ("//div[@id='search-results']//article")
			i_prop = 0

			for result in search_results:
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
				
				if not raw_price or not raw_address or not raw_city or not raw_state:
					continue

				address = ' '.join (' '.join(raw_address).split ()) if raw_address else None
				city = ''.join (raw_city).strip () if raw_city else None
				state = ''.join (raw_state).strip () if raw_state else None
				postal_code = ''.join (raw_postal_code).strip () if raw_postal_code else None
				price = ''.join (raw_price).strip () if raw_price else None
				price = re.sub('[^0-9]','', price)
				info = ' '.join (' '.join (raw_info).split ()).replace (u"\xb7",',')
				title = ''.join (raw_title) if raw_title else None
				property_url = "https://www.zillow.com" + raw_url[0] if raw_url else None 
				zpid = ''.join (raw_zpid).strip () if raw_zpid else None
				zestimate = api.GetZEstimate (zws_id, zpid).get_dict ()['zestimate']['amount']
				latitude = api.GetZEstimate (zws_id, zpid).get_dict ()['full_address']['latitude']
				longitude = api.GetZEstimate (zws_id, zpid).get_dict ()['full_address']['longitude']
				tax_assessment = api.GetZEstimate (zws_id, zpid).get_dict ()['extended_data']['tax_assessment']
				year_built = api.GetZEstimate (zws_id, zpid).get_dict ()['extended_data']['year_built']

				nearby_hospitals = gmaps.places_nearby(type="hospital", location=(latitude, longitude), radius=1000)
				num_nearby_hospitals = len (nearby_hospitals['results'])
				nearby_universities = gmaps.places_nearby(type="university", location=(latitude, longitude), radius=1000)
				num_nearby_universities = len (nearby_universities['results'])
								
				# response = requests.get (property_url, headers=headers, verify=False)

				data = {
					'address':address,
					'city':city,
					'state':state,
					'postal_code':postal_code,
					'price':price,
					'zestimate':zestimate,
					'facts and features':info,
					'url':property_url,
					'title':title,
					'year_built':year_built,
					'tax_assessment':tax_assessment,
					'num_nearby_hospitals':num_nearby_hospitals,
					'num_nearby_universities':num_nearby_universities
				}

				properties_list.append (data)

			if i_prop < 25:
				break

			page_num += 1

		except Exception, e:
			print "Exception: {0}".format(e)

	return properties_list

with open ('zws_key', 'r') as zws_file:
    zws_id = zws_file.read ().replace ('\n', '')

if not zws_id:
	print "Cannot find zillow API key"
	exit

with open ('gapi_key', 'r') as gapi_file:
    google_id = gapi_file.read ().replace ('\n', '')

if not google_id:
	print "Cannot find zillow API key"
	exit

results = parse ("Houston", "TX", 100000, 2)

for result in results:
	if result["zestimate"] / result["price"] > 1.5:
		print "Good value: {0}".format (result["zestimate"] / result["price"])
		print result
	elif result["num_nearby_hospitals"] > 0:
		print "Hospital"
		print result
	elif result["num_nearby_universities"] > 0:
		print "University"
		print result
