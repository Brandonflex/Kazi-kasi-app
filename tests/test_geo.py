"""Distance: cheap, approximate, and honest about both."""

import math

import pytest

from kazikasi import geo


class TestHaversine:
    def test_zero_distance(self):
        point = geo.NAIROBI_AREAS["westlands"]
        assert geo.haversine_km(point, point) == 0

    def test_nairobi_to_mombasa_is_about_440_km(self):
        km = geo.haversine_km(geo.COUNTY_CENTROIDS["Nairobi"], geo.COUNTY_CENTROIDS["Mombasa"])
        assert 420 < km < 460

    def test_cbd_to_westlands_is_a_short_hop(self):
        km = geo.haversine_km(geo.NAIROBI_AREAS["cbd"], geo.NAIROBI_AREAS["westlands"])
        assert 1 < km < 4


class TestBands:
    @pytest.mark.parametrize(
        "km,band",
        [(0, "walkable"), (2.9, "walkable"), (3.1, "one matatu"), (8, "one matatu"),
         (9, "long commute"), (16, "long commute"), (20, "across the metro"),
         (41, "outside the metro")],
    )
    def test_bands(self, km, band):
        assert geo.band_for(km) == band


class TestDistanceBetween:
    def test_same_area_is_zero(self):
        distance = geo.distance_between("Kasarani", "Nairobi", "Kasarani", "Nairobi")
        assert distance.km == 0
        assert distance.band == "walkable"

    def test_area_to_area(self):
        distance = geo.distance_between("Kasarani", "Nairobi", "Westlands", "Nairobi")
        assert 5 < distance.km < 15
        assert distance.approximate is True

    def test_counts_to_label_is_carried(self):
        distance = geo.distance_between("Kilimani", "Nairobi", "Industrial Area", "Nairobi")
        assert distance.from_label == "Kilimani"
        assert distance.to_label == "Industrial Area"

    def test_falls_back_to_county(self):
        distance = geo.distance_between(None, "Nairobi", None, "Kiambu")
        assert distance is not None and distance.km > 0

    def test_unknown_location_is_none_not_guessed(self):
        # A posting with no location is *unknown*, not "nearby".
        assert geo.distance_between("Kasarani", "Nairobi", None, None) is None
        assert geo.distance_between(None, None, "Westlands", "Nairobi") is None

    def test_unknown_county_is_none(self):
        assert geo.coordinates_for("Atlantis", "Nowhere") is None


class TestCommuteUtility:
    def test_decays_with_distance(self):
        assert geo.commute_utility(0) == 1.0
        assert geo.commute_utility(5) == pytest.approx(math.exp(-1.5), rel=1e-6)
        assert geo.commute_utility(5) < geo.commute_utility(1)

    def test_the_research_figure(self):
        # ~4.5x less attractive at +5 km.
        assert geo.commute_utility(0) / geo.commute_utility(5) == pytest.approx(4.48, rel=0.02)

    def test_unknown_is_midpoint_not_zero(self):
        assert geo.commute_utility(None) == 0.5


class TestMetro:
    def test_metro_counties(self):
        assert geo.in_metro("Nairobi") and geo.in_metro("kiambu")
        assert not geo.in_metro("Mombasa")
        assert not geo.in_metro(None)
