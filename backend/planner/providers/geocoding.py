"""Place search: a fallback service, and answers checked and ranked against the words typed.

Free map search is fuzzy. Asked for "asdfgh", Photon answers with an office called
"ADF&G" in Alaska; for "Chicago", with three railway stations named Chicago. So an
answer has to name what was typed, towns and cities come before buildings and
streets, and each label is listed once.
"""

import re
import unicodedata
from collections.abc import Callable
from difflib import SequenceMatcher

from .base import Geocoder, Place, UpstreamUnavailable

ASKED_PER_QUERY = 15  # answers asked of a service per query, before checking and ranking

# A first word searched in full as well: Photon finds bus stops for "Ft Worth".
ABBREVIATIONS = {"ft": "Fort", "mt": "Mount", "st": "Saint", "ste": "Sainte"}
# Names the services do not know: Photon answers "OKC" with a party bus.
NICKNAMES = {
    "nyc": "New York City",
    "okc": "Oklahoma City",
    "slc": "Salt Lake City",
    "nola": "New Orleans",
    "philly": "Philadelphia",
    "vegas": "Las Vegas",
    "indy": "Indianapolis",
    "phx": "Phoenix",
}
# A last part that only names the country is checked, not searched: Photon answers
# "Dallas, TX, USA" with shops that have USA in their names.
COUNTRY_NAMES = {"us", "usa", "united states", "united states of america", "canada", "mexico"}
TYPO_RATIO = 0.8  # how alike a typed word and a name must be: "chicgo" finds "chicago"
TIERS = {"town": 0, "area": 1}  # then everything else: buildings, streets, businesses
MIN_RESPELL_CHARS = 5  # shorter text is still being typed


class FallbackGeocoder:
    """Ask the primary service; ask the fallback if it is down or finds nothing at all.

    The fallback (Nominatim) allows about one request a second and is not meant for
    typing-ahead, so it gets only the text as typed, and only when the primary has
    nothing. When the primary answered but nothing fits the words typed, that is the
    answer: nothing found.
    """

    def __init__(
        self,
        primary: Geocoder,
        fallback: Geocoder,
        spelled_like: Callable[[str], str | None] | None = None,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.spelled_like = spelled_like  # a town name spelled like the text, for typos

    def search(self, query: str, limit: int = 5) -> list[Place]:
        try:
            found, best = self._ask_primary(query, limit)
        except UpstreamUnavailable:
            return best_matches(query, self.fallback.search(query, ASKED_PER_QUERY), limit)
        if found:
            return best
        try:
            return best_matches(query, self.fallback.search(query, ASKED_PER_QUERY), limit)
        except UpstreamUnavailable:
            return []  # the primary has nothing, and the fallback cannot say otherwise

    def _ask_primary(self, query: str, limit: int) -> tuple[list[Place], list[Place]]:
        """Everything the primary found for the query's forms, and what of it fits."""
        found = [
            place
            for variant in query_variants(query)
            for place in self.primary.search(variant, ASKED_PER_QUERY)
        ]
        best = best_matches(query, found, limit)
        if not any(place.kind in TIERS for place in best) and (corrected := self._respell(query)):
            # No town fits, perhaps from a typo: Photon answers "Pheonix" with a shop of
            # that name, never with Phoenix. Search the town spelled like it too.
            found = [*self.primary.search(corrected, ASKED_PER_QUERY), *found]
            best = best_matches(corrected, found, limit) or best
        return found, best

    def _respell(self, query: str) -> str | None:
        main, comma, rest = query.partition(",")
        if not self.spelled_like or len(main.strip()) < MIN_RESPELL_CHARS:
            return None
        if any(char.isdigit() for char in main):
            return None  # a street address, not a misspelt town
        town = self.spelled_like(" ".join(main.split()))
        if not town or _words(town) == _words(main):
            return None
        return town + comma + rest


def query_variants(query: str) -> list[str]:
    """What to search for: "Ft Worth, TX, USA" -> "Fort Worth, TX", then "Ft Worth, TX"."""
    parts = query.split(",")
    if len(parts) > 1 and " ".join(_words(parts[-1])) in COUNTRY_NAMES:
        query = ",".join(parts[:-1])
    main, comma, rest = query.partition(",")
    words = main.split()
    variants = []
    if nickname := NICKNAMES.get(" ".join(_words(main))):
        variants.append(nickname + comma + rest)
    if words and (full := ABBREVIATIONS.get(" ".join(_words(words[0])))):
        variants.append(" ".join([full, *words[1:]]) + comma + rest)
    variants.append(query)
    return list(dict.fromkeys(v.strip() for v in variants))


def best_matches(query: str, places: list[Place], limit: int) -> list[Place]:
    """The places that fit the query, best first, one per label.

    A place fits when its own name or address answers the first part of the query,
    and each later part ("TX", "Texas", "Canada") names where it is. A short code the
    place does not know ("DF" for Mexico City) only ranks it lower: codes have aliases
    this list does not. Towns and areas named exactly as typed come first ("Texas" the
    state, not Texas City), those in the place named after the comma before the rest,
    then towns, areas and everything else. Street addresses keep the service's order.
    """
    names = [_words(variant.partition(",")[0]) for variant in query_variants(query)]
    qualifiers = [part for part in (_words(text) for text in query.split(",")[1:]) if part]
    address = any(word.isdigit() for word in names[-1])

    def rank(item: tuple[int, Place]) -> tuple:
        order, place = item
        tier = 0 if address else TIERS.get(place.kind, 2)
        # A railway called "NYC" is named exactly as typed, but it is not a town.
        exact = tier < 2 and _own_words(place) in names
        words = _own_words(place) + _words(place.address)
        complete = any(all(_known(w, words) for w in _significant(t)) for t in names)
        return (not exact, not _qualified(place, qualifiers), tier, not complete, order)

    fitting = [
        (order, place) for order, place in enumerate(places) if _fits(place, names, qualifiers)
    ]
    best: dict[str, Place] = {}
    for _, place in sorted(fitting, key=rank):
        # "Toronto—Danforth" and "Toronto–Danforth" read the same: list them once.
        best.setdefault(" ".join(_words(place.label)), place)
    return list(best.values())[:limit]


def _fits(place: Place, names: list[list[str]], qualifiers: list[list[str]]) -> bool:
    """The name typed is in the place's own name or address, not just in its county
    or country: a church in Orleans Parish is no answer to "Paris", nor a shop in
    Aguascalientes, Mexico, to "Mexico City"."""
    words = _own_words(place) + _words(place.address)
    if not any(any(_known(w, words) for w in _significant(typed)) for typed in names):
        return False
    words = _surroundings(place)
    return all(
        any(_known(w, words) for w in part) or all(len(w) <= 3 for w in part) for part in qualifiers
    )


def _qualified(place: Place, qualifiers: list[list[str]]) -> bool:
    """Every part after a comma names where the place is, codes included."""
    words = _surroundings(place)
    return all(any(_known(w, words) for w in part) for part in qualifiers)


def _surroundings(place: Place) -> list[str]:
    """Where the place is, which a part after a comma must name: its street, town,
    county, state and country, never its own name ("Hostel DF" is not in DF)."""
    return _words(f"{place.address} {place.region}")


def _own_words(place: Place) -> list[str]:
    """The words of the place's own name: the label before its town, state and country."""
    return _words(place.label.partition(",")[0])


def _known(typed: str, words: list[str]) -> bool:
    """True when the place has a word starting with `typed`, or one a typo away from it."""
    return any(
        word.startswith(typed)
        or (
            len(typed) >= 4
            and word[:2] == typed[:2]
            and SequenceMatcher(None, typed, word).ratio() >= TYPO_RATIO
        )
        for word in words
    )


def _significant(words: list[str]) -> list[str]:
    """The words that identify a place: "paul" in "st paul", unless all are short."""
    return [w for w in words if len(w) >= 3 or w.isdigit()] or words


def _words(text: str) -> list[str]:
    """Lowercase words without accents or punctuation: "Montréal, QC" -> montreal, qc."""
    plain = unicodedata.normalize("NFKD", text)
    plain = "".join(c for c in plain if not unicodedata.combining(c)).casefold()
    return re.findall(r"[a-z0-9]+", plain)
