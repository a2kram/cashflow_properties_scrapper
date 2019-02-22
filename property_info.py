from lxml import html

from selenium import webdriver
from craigslist import CraigslistHousing 
from utilities import print_time, print_err, get_geocode_from_address, get_distance_bw_geocodes, is_digit

import re
import zillow
import urllib3
import requests
import googlemaps


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


headers = {
					'accept':'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
					'accept-encoding':'gzip, deflate, br',
					'accept-language':'en-US,en;q=0.9,ar;q=0.8',
					'cache-control':'max-age=0',
					'upgrade-insecure-requests':'1',
					'user-agent':'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36'
		}


class property_analyzer ():
    def __init__ (self):
        with open ("keys/zws_key", "r") as zws_file:
            self.zws_id = zws_file.read ().replace ("\n", "")

        if not self.zws_id:
            print_err ("Cannot find Zillow API key")

        with open ("keys/gapi_key", "r") as gapi_file:
            google_id = gapi_file.read ().replace ("\n", "")    

        if not google_id:
            print_err ("Cannot find Google API key")

        self.zapi = zillow.ValuationApi ()
        self.gmaps = googlemaps.Client (key=google_id)
        self.browser = None
        # self.browser = webdriver.Chrome ()


    def deinit (self):
        if self.browser:
            self.browser.close ()


    def get_zpid_from_addr (self, address, city, state, zipcode):
        if not address:
            return None
        
        if city and state:
            citystatezip = "{0}, {1}".format (city, state)
        elif zipcode:
            citystatezip = zipcode
        else:
            return None

        try:
            place = self.zapi.GetSearchResults (self.zws_id, address, citystatezip)

            if place:
                return int (place.zpid)
        except:
            return None


    def get_zestimate_info (self, zpid):
        try:
            if not zpid:
                return None, None, None, None

            try:
                zestimate_dict = self.zapi.GetZEstimate (self.zws_id, zpid).get_dict ()
            except:
                return None, None, None, None

            if not zestimate_dict:
                return None, None, None, None

            if "zestimate" in zestimate_dict:
                if "amount" in zestimate_dict["zestimate"]:
                    zestimate = zestimate_dict['zestimate']['amount']

            if "extended_data" in zestimate_dict:
                if "tax_assessment" in zestimate_dict["extended_data"]:
                    tax = zestimate_dict['extended_data']['tax_assessment']

                if "year_built" in zestimate_dict["extended_data"]:
                    year = zestimate_dict['extended_data']['year_built']

            if "full_address" in zestimate_dict:
                if "latitude" in zestimate_dict["full_address"]:
                    latitude = zestimate_dict['full_address']['latitude']

                if "longitude" in zestimate_dict["full_address"]:
                    longitude = zestimate_dict['full_address']['longitude']

            zestimate = int (zestimate) if zestimate else None
            tax = int (tax) if tax else None
            year = int (year) if year else None
            latitude = float (latitude) if latitude else None
            longitude = float (longitude) if longitude else None

            return zestimate, tax, year, (latitude, longitude)
        except Exception, e:
            print "{0}".format (e)


    def get_nearby_info (self, geocode, limit):
        try:
            nearby_hospitals = [] 
            nearby_uni = []

            if not geocode or geocode[0] is None or geocode[1] is None:
                return [], []

            hospitals = self.gmaps.find_place ("hospital", "textquery", fields=["name", "geometry"], 
                location_bias="circle:1000@{0},{1}".format (geocode[0], geocode[1]))
            universities = self.gmaps.find_place ("university", "textquery", fields=["name", "geometry"], 
                location_bias="circle:1000@{0},{1}".format (geocode[0], geocode[1]))
            universities.update (self.gmaps.find_place ("college", "textquery", fields=["name", "geometry"], 
                location_bias="circle:1000@{0},{1}".format (geocode[0], geocode[1])))

            for candidate in hospitals["candidates"]:
                hospital = (candidate["geometry"]["location"]["lat"], candidate["geometry"]["location"]["lng"])

                if get_distance_bw_geocodes (geocode, hospital) < limit:
                    nearby_hospitals.append (str (candidate["name"]))

            for candidate in universities["candidates"]:
                uni = (candidate["geometry"]["location"]["lat"], candidate["geometry"]["location"]["lng"])

                if get_distance_bw_geocodes (geocode, uni) < limit:
                    nearby_uni.append (str (candidate["name"]))

            return nearby_hospitals, nearby_uni
        except Exception, e:
            print "{0}".format (e)


    def get_rental_comps_craigslist (self, address, city, zipcode, limit, bd, ba, sqft):
        if not address or not city or not zipcode or not limit:
            return None

        rents = []
        geocode = get_geocode_from_address (address)

        if not geocode or not bd or not ba or not sqft:
            return None

        try:
            cl_h = CraigslistHousing (site=city.lower (), category="apa", 
                filters={'zip_code':zipcode, 'search_distance':limit, 'min_bedrooms':bd, 'max_bedrooms':bd,
                "min_bathrooms":ba, "max_bathrooms":ba, "min_ft2":max (0, sqft - 300), "max_ft2":sqft + 300,
                'housing_type':['apartment', 'condo', 'house', 'townhouse']})

            for result in cl_h.get_results (geotagged=True):
                dist = get_distance_bw_geocodes (geocode, result["geotag"])

                if dist < limit:
                    rents.append (int (re.sub("[^0-9]","", result["price"])))
        except:
            return None

        if len (rents) > 1:
            return sum (rents) / float (len (rents))
        
        return None


    def get_zillow_rental_info (self, url):
        rental = None
        year = None

        if not self.browser:
            return None, None

        self.browser.get (url)
        button = self.browser.find_elements_by_xpath ("//section[@id='homeValue']")

        if button:
            button[0].click ()

            button = self.browser.find_element_by_link_text ("See more home value estimates")

            if button:
                button.click ()

                parser = html.fromstring (self.browser.page_source)
                rental = parser.xpath (".//h4[@class='zestimate-value ds-standard-label']//text()")
                rental = re.sub ('[^0-9]','', rental)
                year = parser.xpath (".//span[@class='ds-body ds-home-fact-value']//text()")[1]
        else:
            button = self.browser.find_elements_by_xpath ("//div[@class='toggle-section']")

            if button:
                button[0].click()

                parser = html.fromstring (self.browser.page_source)
                rental = parser.xpath (".//div[@class='zestimate-value']//text()")[1]
                rental = re.sub('[^0-9]','', rental)
                year = parser.xpath (".//div[@class='fact-value']//text()")[1]

        return rental, year

    
    def get_info_from_zillow (self, zpid):
        url = "https://www.zillow.com/homedetails/{0}_zpid/".format (zpid)
        response = requests.get (url, headers=headers, verify=False)
        parser = html.fromstring (response.text)

        raw_info = parser.xpath (".//h3[@class='edit-facts-light']//text()")

        if not raw_info:
            return None, None, None

        info = ", ".join (raw_info)

        info = [float (s) for s in info.replace (",", "").split () if is_digit (s)]

        if len (info) != 3:
            return None, None, None
        
        return info[0], info[1], info[2]