from property_info import property_analyzer
from utilities import print_err, get_geocode_from_address


def process_property (address, city, state, zipcode, price):
	prop_analyzer = property_analyzer ()

	zpid = prop_analyzer.get_zpid_from_addr (address, None, None, zipcode)

	if not zpid:
		print_err ("Couldnt find enough info on property")

	bd, ba, sqft = prop_analyzer.get_info_from_zillow (zpid)

	if bd is None or ba is None or sqft is None:
		print_err ("Couldnt find enough info on property")

	rental = prop_analyzer.get_rental_comps_craigslist (address, city, zipcode, 3, bd, ba, sqft)

	if not rental:
		print_err ("Couldnt find enough info on property")

	zestimate, tax, year, geocode = prop_analyzer.get_zestimate_info (zpid)

	if not zestimate:
		print_err ("Couldnt find enough info on property")

	hospital, uni = prop_analyzer.get_nearby_info (geocode, 1)

	value_ratio = price * 1.0 / zestimate * 100
	rental_ratio = rental * 1.0 / price * 100

	positives = {}

	if value_ratio < 50:
		positives["equity-discount"] = round (100 - value_ratio, 2)

	if rental_ratio > 1.5:
		positives["cash-on-cash"] = round (rental_ratio, 2)

	if hospital:
		positives["Nearby hospitals"] = hospital

	if uni:
		positives["Nearby universities"] = uni

	if positives:
		print "Good deal!"
		print positives
	else:
		print "Nothing special about this one."

	
def process_results (results):
	lucratives = []

	print "Analyzing investment opportunities",

	for result in results:
		print ".",

		price = result["price"]
		zestimate = result["zestimate"]
		rental = result["rental"]
		hospitals = result["nearby_hospitals"]
		uni = result["nearby_uni"]

		output = {}

		if price and zestimate:
			value_ratio = price * 1.0 / zestimate * 100

			if value_ratio < 50:
				output["url"] = result["url"]
				output["opportunity"] = {}
				output["opportunity"]["equity-discount"] = round (100 - value_ratio, 2)

				if hospitals:
					output["opportunity"]["Nearby hospitals"] = hospitals

				if uni:
					output["opportunity"]["Nearby universities"] = uni
		
		if rental and price: 
			rental_ratio = rental * 1.0 / price * 100

			if rental_ratio > 1.5:
				if not output:
					output["url"] = result["url"]
					output["opportunity"] = {}
					
					if hospitals:
						output["opportunity"]["Nearby hospital"] = hospitals

					if uni:
						output["opportunity"]["Nearby universities"] = uni

				output["opportunity"]["cash-on-cash"] = round (rental_ratio, 2)

		if output:
			lucratives.append (output)

	for i_prop, prop in enumerate (lucratives):
		print ""
		print "{0}) {1}".format (i_prop + 1, prop["url"])
		print prop["opportunity"]

# process_property ("1220 Lorraine Rd", "Wheaton", "IL", "60187", 80000)