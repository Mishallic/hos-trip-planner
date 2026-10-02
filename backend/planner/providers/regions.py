"""Short region codes for the US, Canada and Mexico, as written in log remarks."""

import unicodedata

COUNTRIES = {"US": "USA", "CA": "Canada", "MX": "Mexico"}

US_STATES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "District of Columbia": "DC",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL",
    "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
    "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI",
    "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO", "Montana": "MT",
    "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ",
    "New Mexico": "NM", "New York": "NY", "North Carolina": "NC", "North Dakota": "ND",
    "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA", "Puerto Rico": "PR",
    "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN",
    "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
    "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}  # fmt: skip

CA_PROVINCES = {
    "Alberta": "AB", "British Columbia": "BC", "Manitoba": "MB", "New Brunswick": "NB",
    "Newfoundland and Labrador": "NL", "Northwest Territories": "NT", "Nova Scotia": "NS",
    "Nunavut": "NU", "Ontario": "ON", "Prince Edward Island": "PE", "Quebec": "QC",
    "Saskatchewan": "SK", "Yukon": "YT",
}  # fmt: skip

# ISO 3166-2:MX codes.
MX_STATES = {
    "Aguascalientes": "AGU", "Baja California": "BCN", "Baja California Sur": "BCS",
    "Campeche": "CAM", "Chiapas": "CHP", "Chihuahua": "CHH", "Ciudad de Mexico": "CMX",
    "Mexico City": "CMX", "Coahuila": "COA", "Coahuila de Zaragoza": "COA", "Colima": "COL",
    "Durango": "DUR", "Guanajuato": "GUA", "Guerrero": "GRO", "Hidalgo": "HID",
    "Jalisco": "JAL", "Mexico": "MEX", "State of Mexico": "MEX", "Michoacan": "MIC",
    "Michoacan de Ocampo": "MIC", "Morelos": "MOR", "Nayarit": "NAY", "Nuevo Leon": "NLE",
    "Oaxaca": "OAX", "Puebla": "PUE", "Queretaro": "QUE", "Quintana Roo": "ROO",
    "San Luis Potosi": "SLP", "Sinaloa": "SIN", "Sonora": "SON", "Tabasco": "TAB",
    "Tamaulipas": "TAM", "Tlaxcala": "TLA", "Veracruz": "VER",
    "Veracruz de Ignacio de la Llave": "VER", "Yucatan": "YUC", "Zacatecas": "ZAC",
}  # fmt: skip


def _plain(text: str) -> str:
    """Casefolded, without accents: "Nuevo León" and "nuevo leon" match."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold().strip()


_CODES = {
    country: {_plain(name): code for name, code in table.items()}
    for country, table in (("US", US_STATES), ("CA", CA_PROVINCES), ("MX", MX_STATES))
}


def region_code(state: str | None, country_code: str | None) -> str | None:
    """ "Illinois", "US" -> "IL". Unknown names come back unchanged."""
    if not state:
        return None
    table = _CODES.get((country_code or "").upper(), {})
    return table.get(_plain(state), state)


def is_supported(country_code: str | None) -> bool:
    return (country_code or "").upper() in COUNTRIES
