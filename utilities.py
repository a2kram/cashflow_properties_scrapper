import time
from geopy.geocoders import Nominatim
from geopy.distance import great_circle


def is_digit (x):
    try:
        float (x)
        return True
    except ValueError:
        return False


def print_time (task, start):
	print "{0} took {1}".format (task, time.time () - start)


def print_err (err_desc):
	print "Error! {0}".format (err_desc)
	exit ()


def get_geocode_from_address (address):
	geolocator = Nominatim ()
	location = geolocator.geocode (address)

	if location:
		return (location.latitude, location.longitude)
	else:
		return None


def get_distance_bw_geocodes (loc1, loc2):
	return great_circle (loc1, loc2).miles

        