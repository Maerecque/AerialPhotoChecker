from FlightRadar24 import FlightRadar24API
import numpy as np
import ast
import datetime
from geopy.geocoders import Photon
import geopy.exc

# Idea: use an Ini file to store the center_coordinate, radius, excluded_manufacturers, print_all and other settings
# Center_coordinate = 52.089805, 5.1075
# Radius = 50000
# Excluded_manufacturers = Airbus, Embraer, Bombardier, Boeing
# Print_all = False
# Output_file = flights_over_area.txt
# max_alt = 10000


# Idea: Connect this script to a pipeline that runs every 5 minutes to check for flights going back and forth over the area and save the results to a file

# Idea: Connect this script to an email service to send an email notification when a flight is going back and forth over the area, that will update daily.

def get_coordinates_by_address_via_user_input(print_info: bool = False) -> tuple:
    """
    Retrieves the coordinates of a location based on the address.

    Args:
        print_info (bool, optional): Whether to print the location details or not. Defaults to False.

    Returns:
        tuple: The coordinates of the location (latitude, longitude).

    Raises:
        TypeError: If the address is not a string.

    Notes:
        - Uses geopy module for fetching coordinates.

    """
    # Make 3 attempts to an address
    for _ in range(3):
        address = input("Enter the address: ")

        if not isinstance(address, str):
            raise TypeError("Address must be a string.")

        if address:
            break

    if not address:
        return None

    # Try to find the location based on the address
    try:
        geolocator = Photon(user_agent="geoapiExercises")

    except Exception as e:
        print(f"Error: {e}")
        return None

    try:
        location = geolocator.geocode(address)

    except geopy.exc.GeocoderUnavailable as e:
        print(f"Geocoder is unavailable, you probably reached the limit of requests. See error below:\n{e}")
        return None

    if location is not None:
        if print_info:
            print("Location Details:")
            print(f"Latitude: {location.latitude}, Longitude: {location.longitude}")
            print(f"Address: {location.address}")

        # Convert the coordinates to a tuple and return them
        return location.latitude, location.longitude, location.address

    else:
        print("Location not found. Please try again.")


def get_flights_over_area(center_coordinate: tuple, radius: int, excluded_manufacturers: list, print_all: bool = False) -> list:
    """
    Retrieves flights over a specified area based on the center coordinate, radius, and excluded manufacturers.

    Args:
        center_coordinate (tuple): The center coordinate of the area (latitude, longitude). *Expressed in decimal degrees.*
        radius (int): The radius of the area within which to search for flights, expressed in meters.
        excluded_manufacturers (list): A list of manufacturers to exclude from the results.
        print_all (bool, optional): Whether to print flight details or not. Defaults to True.

    Returns:
        list: A list of flights over the specified area, each represented as a tuple containing the owner and model.
              Returns None if no flights are found.

    Raises:
        TypeError: If the center_coordinate is not a tuple or radius is not an integer.
        ValueError: If radius is less than or equal to 0.

    Notes:
        - Uses fr_api module for fetching flight data.
        - The model and owner information is retrieved from flight details.
        - Case-insensitive comparison for excluded manufacturers.

    """

    if not isinstance(center_coordinate, tuple) or len(center_coordinate) != 2:
        raise TypeError("center_coordinate must be a tuple of (latitude, longitude).")

    if not isinstance(radius, int) or radius <= 0:
        raise ValueError("radius must be a positive integer.")

    flights_over_area = []

    # Get geographical bounds based on center coordinate and radius
    bounds = fr_api.get_bounds_by_point(center_coordinate[0], center_coordinate[1], radius)

    # Fetch flights within the specified bounds
    flights = fr_api.get_flights(bounds=bounds)

    for flight in flights:
        flight_details = fr_api.get_flight_details(flight)

        # Get aircraft model and owner information
        model = flight_details.get('aircraft', {}).get('model', {}).get('text')
        callsign = flight_details.get('identification', {}).get('callsign', '')

        try:
            owner = flight_details.get('airline', {}).get('name', '')

        except AttributeError:
            owner = "Unknown"

        # For the future, do something with the trail of the flight
        trail = flight_details.get('trail', {})

        # Print flight details if print_all is True
        if print_all:
            print("Flight Details:")
            print(f"- Model: {model}")
            print(f"- Owner: {owner}")

        try:
            # Check if the model's manufacturer is not in the excluded manufacturers list
            if not any(model.lower().startswith(manufacturer.lower()) for manufacturer in excluded_manufacturers):
                flights_over_area.append((f"Owner: {owner}", f"Callsign: {callsign}", f"Model: {model}", f"Trail: {trail}"))

        except AttributeError:
            if type(model) is not str:
                model = "Unknown"

        # Check if the model's manufacturer is not in the excluded manufacturers list
        if not any(model.lower().startswith(manufacturer.lower()) for manufacturer in excluded_manufacturers):
            flights_over_area.append((f"Owner: {owner}", f"Callsign: {callsign}", f"Model: {model}", f"Trail: {trail}"))

    if not flights_over_area:
        print("No flights found over the specified area.")
        return None

    return flights_over_area


def check_flight_direction(flights_over_area: list, print_all: bool = False, max_alt: int = 5000) -> list:
    """
    Check the flight direction of flights over a specific area.

    Args:
        flights_over_area (list): A list of flight data tuples, where each tuple contains information about a flight.
        print_all (bool, optional): Whether to print all the results. Defaults to False.
        max_alt (int, optional): The maximum altitude to consider a flight flying at a low altitude, expressed in meters. Defaults to 3000.

    Returns:
        list: A list of flight data tuples for flights that are going back and forth over the area.

    Raises:
        None
    """
    photo_flight_list = []

    for flight in flights_over_area:
        # Extract headings from the "Trail" part of the input tuple
        trail = flight[3]
        headings = []

        # Convert the trail string to a list of dictionaries
        trail = trail.split('[')[1].split(']')[0]

        data_list = ast.literal_eval(f"[{trail}]")

        # Extract 'hd' values from each dictionary in the trail_list
        headings = [point['hd'] for point in data_list]

        flight_height = [point['alt'] for point in data_list]

        # # take the last 70% of the recorded trail points
        # headings = headings[int(len(headings) * 0.3):]

        # Combine the headings of the trail points
        combined_headings = np.array(headings)

        # Split the combined headings into 2 halves based on the 180-degree mark
        half1 = combined_headings[combined_headings < 180]
        half2 = combined_headings[combined_headings >= 180]

        # Check if the flight is going back and forth over the area
        if len(half1) < 10 or len(half2) < 10:
            continue

        # Sort the headings in each half
        half1_sorted = np.sort(half1)
        half2_sorted = np.sort(half2)

        # Find the median, the mode, the average, and the standard deviation of the headings in each half
        half1_median = np.median(half1_sorted)
        half2_median = np.median(half2_sorted)

        try:
            half1_mode = int(np.argmax(np.bincount(half1_sorted)))  # Convert mode to integer
            half2_mode = int(np.argmax(np.bincount(half2_sorted)))  # Convert mode to integer

            half1_avg = np.mean(half1_sorted)
            half2_avg = np.mean(half2_sorted)

            half1_std = np.std(half1_sorted)
            half2_std = np.std(half2_sorted)

        except ValueError:
            continue

        # Check if the flight is flying at a avarage low altitude
        if 500 <= np.mean(flight_height) <= max_alt:
            print(f"Flight: {flight[1].replace('Callsign: ', '')} is flying at an altitude of {round(np.mean(flight_height), 0)} meters with a {flight[2].replace('Model: ', '')}.")

        # If the flight is not flying at a low altitude, continue to the next flight
        else:
            continue

        if print_all:
            # Print the results
            print("Results:")
            print(f"Half 1 - Median: {half1_median}, Mode: {half1_mode}, Average: {half1_avg}, Standard Deviation: {half1_std}")
            print(f"Half 2 - Median: {half2_median}, Mode: {half2_mode}, Average: {half2_avg}, Standard Deviation: {half2_std}")

        # Check if the flight is going back and forth over the area
        # Do this by adding 180 to the mode of the first half and checking if it is close to the mode of the second half (give or take 5 degrees)
        if -5 <= half1_mode + 180 - half2_mode <= 5:

            # Save the date and time of the flight
            date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

            # Add the date and time to the flight tuple
            flight = (flight[0], flight[1], flight[2], f"Date: {date}")

            if print_all:
                print(f"{flight[0]} is flying back and forth over the area: \n {flight[1]} \n {flight[2]} \n {flight[3]}")

            # Check if the flight is flying at a low altitude above the ground
            if 500 <= np.mean(flight_height) <= max_alt:
                # Add the flight to the photo_flight_list
                photo_flight_list.append(flight)

    return photo_flight_list


def write_recorded_flights_away(flights_over_area: list, file_name: str):
    """
    Write the recorded flights that are not going back and forth over the area to a file.

    Args:
        flights_over_area (list): A list of flight data tuples for flights that are not going back and forth over the area.
        file_name (str): The name of the file to write the flights to.

    Returns:
        None

    Raises:
        TypeError: If the flights_over_area is not a list or file_name is not a string.

    Notes:
        - Each flight is written to the file as a separate line.
        - If a flight is recorded multiple times in one day, only the latest record is saved.
    """
    # Check if the flights_over_area is a list
    if not isinstance(flights_over_area, list):
        raise TypeError("flights_over_area must be a list.")

    # Check if the file_name is a string
    if not isinstance(file_name, str):
        raise TypeError("file_name must be a string.")

    # Read the existing flights from the file on the current day
    with open(file_name, 'r') as file:
        existing_flights = file.readlines()

    # Search for all recorded flights that are on this day
    recorded_flights_today = [flight for flight in existing_flights if flight.split('Date: ')[1].split(' ')[0] == datetime.datetime.now().strftime("%Y-%m-%d")]

    # Extract the callsigns of the recorded flights
    recorded_callsigns = [flight.split('Callsign: ')[1].split('\n')[0] for flight in recorded_flights_today]

    # Check if the flight is not already recorded today
    for flight in flights_over_area:
        if flight[1].split('Callsign: ')[1] not in recorded_callsigns:
            # Write the flight to the file
            with open(file_name, 'a') as file:
                file.write(f"{flight[0]} \n {flight[1]} \n {flight[2]} \n {flight[3]} \n")
                print(f"Flight: {flight[1].split('Callsign: ')[1]} is recorded in the file.")


if __name__ == "__main__":
    # Initialize the API
    fr_api = FlightRadar24API()

    # Define the center coordinate and radius (in kilometers)
    center_coordinate = (52.089805, 5.1075)  # Coordinaten van Stadplateau 1, Utrecht op DD formaat
    radius = 20000  # Radius in meters

    # List of manufacturers to exclude
    excluded_manufacturers = ["Airbus", "Embraer", "Bombardier", "Boeing"]

    # Filter to show flight details
    print_all = False

    location_data = get_coordinates_by_address_via_user_input()

    if location_data is None:
        print("No location data found. Using default location.")
        center_coordinate = (52.089805, 5.1075)
    else:
        center_coordinate = location_data[:2]

        print(f"Used address: {location_data[2]}")

    # Get flights over the specified area excluding certain manufacturers
    flights_over_area = get_flights_over_area(center_coordinate, radius, excluded_manufacturers)

    if flights_over_area is None:
        exit()

    aireal_photo_flight = check_flight_direction(flights_over_area)

    if not aireal_photo_flight:
        print("No flights are going back and forth over the area.")
        exit()

    # print information about the flights that are going back and forth over the area, with the trail
    for flight in aireal_photo_flight:
        print(f"Flight: flying back and forth over the area: \n {flight[0]} \n {flight[1]} \n {flight[2]} \n {flight[3]}")

    # Write the recorded flights that are not going back and forth over the area to a file
    write_recorded_flights_away(flights_over_area, "flights_over_area.txt")
