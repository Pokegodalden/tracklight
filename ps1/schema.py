"""Explicit eight-file input contract; values are never silently repaired."""

# kind: text, identifier, integer minimum, flag, priority, date, workload.
SCHEMAS = {
    "01_LINES.csv": {"line_code": "id", "line_name": "text"},
    "02_STATIONS.csv": {"station_id": "id", "line_code": "id", "seq": "positive",
                        "is_interchange": "flag"},
    "03_SECTORS.csv": {"sector_id": "id", "line_code": "id", "from_station_id": "id",
                       "to_station_id": "id", "seq": "positive", "is_shared": "flag"},
    "04_LOCATION_SUPPLY.csv": {"location_id": "id", "location_kind": "text", "line_code": "id",
                               "bound": "text", "supply_capacity": "nonnegative"},
    "05_BUFFER_LOCATION.csv": {"nature_of_works": "text", "up_to_buffer_sectors": "nonnegative",
                               "opposite_bound_required": "flag"},
    "06_PARAMETERS.csv": {"key": "id", "value": "text"},
    "07_PROJECT_DETAILS.csv": {
        "contract_number": "id", "contract_description": "text", "contract_award_date": "date",
        "activity_type": "text", "nature_of_activity": "text", "contract_priority": "priority",
        "contract_completion_date": "date", "planned_completion_date": "date",
        "number_of_workfronts": "nonnegative", "access_type": "text",
        "number_of_maximum_access_per_week": "nonnegative"},
    "08_ACTIVITY_DETAILS.csv": {
        "activity_id": "id", "contract_number": "id", "activity_type": "text",
        "start_location_id": "id", "end_location_id": "id", "total_accesses": "workload",
        "planned_start_date": "date", "predecessor_activity_id": "optional_id",
        "activity_priority": "priority"},
}

KEYS = {
    "01_LINES.csv": ("line_code",),
    "02_STATIONS.csv": ("line_code", "station_id"),
    "03_SECTORS.csv": ("sector_id",),
    "04_LOCATION_SUPPLY.csv": ("location_id",),
    "05_BUFFER_LOCATION.csv": ("nature_of_works",),
    "06_PARAMETERS.csv": ("key",),
    "07_PROJECT_DETAILS.csv": ("contract_number", "activity_type"),
    "08_ACTIVITY_DETAILS.csv": ("activity_id",),
}

BOUNDS = ("EB", "WB")
NATURES = ("Live", "Non-live (Consist)", "Non-live (Others)")
ACCESS_TYPES = ("PM", "PC", "C")
