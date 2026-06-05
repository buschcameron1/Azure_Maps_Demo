import math
import asyncio
import json
from typing import List, Dict, Tuple
from flask import Flask, render_template, request, jsonify
from azure.core.credentials import AzureKeyCredential
from azure.maps.search import MapsSearchClient
from azure.maps.route import MapsRouteClient
from azure.maps.route.models import LatLongPair
from azure.identity.aio import DefaultAzureCredential
from msgraph import GraphServiceClient
from msgraph.generated.users.users_request_builder import UsersRequestBuilder
from kiota_abstractions.base_request_configuration import RequestConfiguration

with open("config.json", "r", encoding="utf-8") as f:
    MAPS_SUBSCRIPTION_KEY = json.load(f).get("MAPS_SUBSCRIPTION_KEY", "")

if MAPS_SUBSCRIPTION_KEY == "":
    raise RuntimeError(
        "MAPS_SUBSCRIPTION_KEY is missing in config.json. "
        "Please add your Azure Maps subscription key to config.json or set AZURE_MAPS_KEY environment variable."
    )

GRAPH_SCOPES = ["https://graph.microsoft.com/.default"]

app = Flask(__name__)

maps_search_client = MapsSearchClient(credential=AzureKeyCredential(MAPS_SUBSCRIPTION_KEY))
maps_route_client = MapsRouteClient(credential=AzureKeyCredential(MAPS_SUBSCRIPTION_KEY))

# Global cache for employees and offices
_employees_cache: List[Dict] = []
_offices_cache: List[str] = []


def geocode_address(address: str) -> Tuple[float, float]:
    """
    Geocode an address to latitude and longitude.
    
    Args:
        address: Street address to geocode
        
    Returns:
        Tuple of (latitude, longitude)
    """
    try:
        search_result = maps_search_client.get_geocoding(query=address)
        if search_result:
            position = search_result['features'][0]["geometry"]["coordinates"]
            return (position[1], position[0])
        else:
            raise ValueError(f"No results found for address: {address}")
    except Exception as e:
        print(f"Error geocoding address '{address}': {e}")
        raise


def get_driving_route(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float) -> List[List[float]]:
    """
    Get driving route coordinates between two points using Azure Maps Route API.

    Returns:
        List of [lon, lat] pairs representing the route polyline
    """
    result = maps_route_client.get_route_directions(
        route_points=[
            LatLongPair(latitude=origin_lat, longitude=origin_lon),
            LatLongPair(latitude=dest_lat, longitude=dest_lon),
        ]
    )
    coords = []
    for leg in result.routes[0].legs:
        for point in leg.points:
            coords.append([point.longitude, point.latitude])
    return coords


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate straight-line distance between two coordinates using Haversine formula.
    
    Args:
        lat1, lon1: First coordinate (latitude, longitude)
        lat2, lon2: Second coordinate (latitude, longitude)
        
    Returns:
        Distance in kilometers
    """
    R = 6371  # Earth's radius in km
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c


def find_nearest_office(employee: Dict, office_coords: Dict[str, Tuple[float, float]]) -> Dict:
    """Find the nearest office for a given employee."""
    address = employee["address"]
    try:
        emp_lat, emp_lon = geocode_address(address)

        distances = {}
        for office_name, (office_lat, office_lon) in office_coords.items():
            distances[office_name] = haversine_distance(emp_lat, emp_lon, office_lat, office_lon)

        nearest_office = min(distances, key=distances.get)
        return {
            "name": employee["name"],
            "address": address,
            "nearest_office": nearest_office,
            "distance_km": round(distances[nearest_office], 2),
        }
    except Exception as e:
        return {
            "name": employee["name"],
            "address": address,
            "error": str(e),
        }


async def get_employee_addresses(graph_client: GraphServiceClient) -> List[Dict]:
    """Fetch employees and their addresses from the Graph /users API."""
    config = RequestConfiguration(
        query_parameters=UsersRequestBuilder.UsersRequestBuilderGetQueryParameters(
            select=["displayName", "streetAddress", "city", "state", "postalCode", "country"]
        )
    )
    response = await graph_client.users.get(request_configuration=config)

    employees = []
    while response:
        for user in response.value or []:
            parts = [user.street_address, user.city, user.state, user.postal_code, user.country]
            address = ", ".join(p for p in parts if p)
            if address:
                employees.append({"name": user.display_name or "Unknown", "address": address})

        # Handle pagination
        if response.odata_next_link:
            response = await graph_client.users.with_url(response.odata_next_link).get()
        else:
            break

    return employees


def get_office_locations(config_file: str = "offices.json") -> List[str]:
    """Load office building addresses from a JSON configuration file."""
    try:
        with open(config_file, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Office configuration file '{config_file}' not found. Create it first.")
    except json.JSONDecodeError:
        raise ValueError(f"Office configuration file '{config_file}' is not valid JSON.")

    offices = []
    for place in data.get("value", []):
        address_obj = place.get("address")
        if address_obj:
            parts = [
                address_obj.get("street"),
                address_obj.get("city"),
                address_obj.get("state"),
                address_obj.get("postalCode"),
                address_obj.get("countryOrRegion"),
            ]
            address = ", ".join(p for p in parts if p)
            if address:
                offices.append(address)

    return offices


def print_results(results: List[Dict]) -> None:
    """Pretty print the results."""
    print("\n" + "=" * 80)
    print("RESULTS: Nearest Office for Each Employee")
    print("=" * 80 + "\n")

    for result in results:
        if "error" in result:
            print(f"Employee: {result['name']}")
            print(f"Address:  {result['address']}")
            print(f"Error:    {result['error']}\n")
        else:
            print(f"Employee:       {result['name']}")
            print(f"Address:        {result['address']}")
            print(f"Nearest Office: {result['nearest_office']}")
            print(f"Distance:       {result['distance_km']} km\n")


async def main():
    credential = DefaultAzureCredential()
    graph_client = GraphServiceClient(credentials=credential, scopes=GRAPH_SCOPES)

    try:
        print("Fetching employee addresses from Microsoft Graph /users...")
        employees = await get_employee_addresses(graph_client)
        print(f"Found {len(employees)} employees with addresses\n")

        print("Loading office locations from offices.json...")
        office_locations = get_office_locations()
        print(f"Found {len(office_locations)} office locations\n")

        if not employees:
            print("No employees with addresses found.")
            return
        if not office_locations:
            print("No office locations found in the Places API.")
            return

        print("Geocoding office locations...")
        office_coords: Dict[str, Tuple[float, float]] = {}
        for office in office_locations:
            try:
                coords = geocode_address(office)
                office_coords[office] = coords
                print(f"  ✓ {office}: {coords}")
            except Exception as e:
                print(f"  ✗ Failed to geocode '{office}': {e}")

        if not office_coords:
            raise ValueError("No office locations could be geocoded")

        print(f"\nFinding nearest office for {len(employees)} employees...")
        results = []
        for i, employee in enumerate(employees, 1):
            print(f"  [{i}/{len(employees)}] {employee['name']} — {employee['address']}")
            result = find_nearest_office(employee, office_coords)
            results.append(result)
            if "error" not in result:
                print(f"       → Nearest: {result['nearest_office']} ({result['distance_km']} km)")
            else:
                print(f"       → Error: {result['error']}")

        print_results(results)
    finally:
        await credential.close()


async def initialize_app():
    """Initialize app with cached data."""
    global _offices_cache
    
    try:
        print("Initializing app: Loading offices...")
        _offices_cache = get_office_locations()
        print(f"Loaded {len(_offices_cache)} offices")
    except Exception as e:
        print(f"Error initializing app: {e}")


@app.route("/")
def index():
    """Serve the main web interface."""
    return render_template("index.html", maps_key=MAPS_SUBSCRIPTION_KEY)


@app.route("/api/users", methods=["GET"])
def api_users():
    """Get list of employees from Graph API."""
    global _employees_cache
    
    if not _employees_cache:
        try:
            # Run async function synchronously
            credential = DefaultAzureCredential()
            graph_client = GraphServiceClient(credentials=credential, scopes=GRAPH_SCOPES)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                _employees_cache = loop.run_until_complete(get_employee_addresses(graph_client))
            finally:
                loop.close()
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    return jsonify([
        {"id": i, "name": emp["name"], "address": emp["address"]}
        for i, emp in enumerate(_employees_cache)
    ])


@app.route("/api/offices", methods=["GET"])
def api_offices():
    """Get list of offices."""
    return jsonify(_offices_cache)


@app.route("/api/nearest-office", methods=["POST"])
def api_nearest_office():
    """Find nearest office for a given employee."""
    data = request.json
    employee_id = data.get("employee_id")
    
    if employee_id is None or employee_id >= len(_employees_cache):
        return jsonify({"error": "Invalid employee ID"}), 400
    
    employee = _employees_cache[employee_id]
    
    try:
        emp_lat, emp_lon = geocode_address(employee["address"])
        
        office_coords: Dict[str, Tuple[float, float]] = {}
        for office in _offices_cache:
            try:
                office_coords[office] = geocode_address(office)
            except:
                pass
        
        if not office_coords:
            return jsonify({"error": "No offices could be geocoded"}), 400
        
        distances = {}
        for office_name, (office_lat, office_lon) in office_coords.items():
            distances[office_name] = haversine_distance(emp_lat, emp_lon, office_lat, office_lon)
        
        nearest_office = min(distances, key=distances.get)
        nearest_coords = office_coords[nearest_office]

        # Get driving route from Azure Maps Route API
        route_coords = get_driving_route(
            emp_lat, emp_lon,
            nearest_coords[0], nearest_coords[1]
        )

        return jsonify({
            "employee": employee,
            "employee_coords": {"lat": emp_lat, "lon": emp_lon},
            "nearest_office": nearest_office,
            "office_coords": {"lat": nearest_coords[0], "lon": nearest_coords[1]},
            "distance_km": round(distances[nearest_office], 2),
            "route_coords": route_coords,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        # Run as Flask app
        asyncio.run(initialize_app())
        app.run(debug=True, port=5000)
    else:
        # Run the old CLI version
        asyncio.run(main())