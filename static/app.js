const mapsKey = document.querySelector('meta[name="maps-key"]').content;
let map;
let datasource = null;
let symbolLayer = null;
let lineLayer = null;

// Initialize map
function initMap() {
    map = new atlas.Map("map", {
        center: [-95.7129, 37.0902],
        zoom: 4,
        authOptions: {
            authType: "subscriptionKey",
            subscriptionKey: mapsKey
        }
    });
    map.events.add("ready", () => {
        datasource = new atlas.source.DataSource();
        map.sources.add(datasource);
    });
}

// Load employees on page load
async function loadEmployees() {
    try {
        const response = await fetch("/api/users");
        const employees = await response.json();

        const select = document.getElementById("employee-select");
        select.innerHTML = '<option value="">-- Select an employee --</option>';

        employees.forEach(emp => {
            const option = document.createElement("option");
            option.value = emp.id;
            option.textContent = emp.name;
            select.appendChild(option);
        });

        select.addEventListener("change", () => {
            document.getElementById("find-office-btn").disabled = select.value === "";
        });
    } catch (error) {
        showError("Failed to load employees: " + error.message);
    }
}

// Find nearest office
async function findNearestOffice() {
    const employeeId = document.getElementById("employee-select").value;
    if (employeeId === "") {
        showError("Please select an employee");
        return;
    }

    try {
        const response = await fetch("/api/nearest-office", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ employee_id: parseInt(employeeId) })
        });

        if (!response.ok) {
            const error = await response.json();
            showError(error.error || "Failed to find office");
            return;
        }

        const result = await response.json();
        displayResults(result);
        displayRoute(result);
    } catch (error) {
        showError("Error: " + error.message);
    }
}

// Display results in sidebar
function displayResults(result) {
    document.getElementById("result-name").textContent = result.employee.name;
    document.getElementById("result-address").textContent = result.employee.address;
    document.getElementById("result-office").textContent = result.nearest_office;
    document.getElementById("result-distance").textContent = result.distance_km + " km";
    document.getElementById("results").classList.remove("hidden");
    document.getElementById("error").classList.add("hidden");
}

// Display driving route on map
function displayRoute(result) {
    if (!map || !datasource) return;

    datasource.clear();
    if (symbolLayer) map.layers.remove(symbolLayer);
    if (lineLayer) map.layers.remove(lineLayer);

    const employeePin = new atlas.data.Feature(
        new atlas.data.Point([result.employee_coords.lon, result.employee_coords.lat]),
        { title: "Employee", color: "blue" }
    );
    const officePin = new atlas.data.Feature(
        new atlas.data.Point([result.office_coords.lon, result.office_coords.lat]),
        { title: result.nearest_office, color: "red" }
    );

    const routeCoords = result.route_coords && result.route_coords.length > 1
        ? result.route_coords
        : [
            [result.employee_coords.lon, result.employee_coords.lat],
            [result.office_coords.lon, result.office_coords.lat]
        ];

    const routeLine = new atlas.data.Feature(new atlas.data.LineString(routeCoords));

    datasource.add([routeLine, employeePin, officePin]);

    lineLayer = new atlas.layer.LineLayer(datasource, null, {
        strokeColor: "#0078d4",
        strokeWidth: 4,
        filter: ["==", "$type", "LineString"]
    });
    map.layers.add(lineLayer);

    symbolLayer = new atlas.layer.SymbolLayer(datasource, null, {
        filter: ["!=", "$type", "LineString"],
        iconOptions: {
            image: ["case",
                ["==", ["get", "color"], "blue"], "pin-blue",
                ["==", ["get", "color"], "red"], "pin-red",
                "pin-blue"
            ],
            size: 0.5
        },
        textOptions: {
            textField: ["get", "title"],
            offset: [0, 1.2],
            size: 12
        }
    });
    map.layers.add(symbolLayer);

    const bounds = atlas.data.BoundingBox.fromData([employeePin, officePin]);
    map.setCamera({ bounds: bounds, padding: 80 });
}

function showError(message) {
    document.getElementById("error").textContent = message;
    document.getElementById("error").classList.remove("hidden");
}

document.getElementById("find-office-btn").addEventListener("click", findNearestOffice);

window.addEventListener("load", () => {
    initMap();
    loadEmployees();
});
