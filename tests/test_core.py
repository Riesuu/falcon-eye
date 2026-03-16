# -*- coding: utf-8 -*-
"""
Tests unitaires — BMS GCI Radar v5
Couvre: core/data.py, core/trtt_client.py, core/mission_parser.py
"""
import sys, os, math, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest

# ═══════════════════════════════════════════════════════════════════════════════
# TESTS : core/data.py
# ═══════════════════════════════════════════════════════════════════════════════
from core.data import (haversine_nm, bearing_deg, braa_str, bullseye_str,
                        bms_to_latlon, AIRPORTS, COASTLINE_KOREA, DMZ_LINE,
                        RUNWAY_POLYGONS)


class TestHaversine(unittest.TestCase):
    def test_zero_distance(self):
        self.assertAlmostEqual(haversine_nm(37.5, 127.0, 37.5, 127.0), 0.0, places=5)

    def test_known_distance(self):
        """Osan (37.09, 127.03) → Gunsan (35.91, 126.62) ≈ 73 NM"""
        d = haversine_nm(37.09, 127.03, 35.91, 126.62)
        self.assertAlmostEqual(d, 73.0, delta=3.0)

    def test_symmetry(self):
        d1 = haversine_nm(37.0, 127.0, 38.0, 128.0)
        d2 = haversine_nm(38.0, 128.0, 37.0, 127.0)
        self.assertAlmostEqual(d1, d2, places=6)

    def test_large_distance(self):
        """Seoul → Pyongyang ≈ 120 NM"""
        d = haversine_nm(37.55, 126.97, 39.02, 125.73)
        self.assertAlmostEqual(d, 104.0, delta=8.0)


class TestBearing(unittest.TestCase):
    def test_north(self):
        b = bearing_deg(37.0, 127.0, 38.0, 127.0)
        self.assertAlmostEqual(b, 0.0, delta=1.0)

    def test_east(self):
        b = bearing_deg(37.0, 127.0, 37.0, 128.0)
        self.assertAlmostEqual(b, 90.0, delta=2.0)

    def test_south(self):
        b = bearing_deg(38.0, 127.0, 37.0, 127.0)
        self.assertAlmostEqual(b, 180.0, delta=1.0)

    def test_west(self):
        b = bearing_deg(37.0, 128.0, 37.0, 127.0)
        self.assertAlmostEqual(b, 270.0, delta=2.0)

    def test_range_0_360(self):
        for lat2, lon2 in [(38, 128), (36, 126), (38, 126), (36, 128)]:
            b = bearing_deg(37.0, 127.0, lat2, lon2)
            self.assertGreaterEqual(b, 0.0)
            self.assertLess(b, 360.0)


class TestBraaStr(unittest.TestCase):
    def test_format(self):
        s = braa_str(37.0, 127.0, 38.0, 128.0)
        # Format: "BRG / RNG NM"
        parts = s.split("/")
        self.assertEqual(len(parts), 2)
        self.assertIn("NM", parts[1])

    def test_three_digit_bearing(self):
        s = braa_str(37.0, 127.0, 37.0, 127.001)
        self.assertEqual(len(s.split("/")[0].strip()), 3)


class TestBullseyeStr(unittest.TestCase):
    def test_format(self):
        s = bullseye_str(37.0, 127.0, 38.0, 128.0, 25000)
        parts = s.split("/")
        self.assertEqual(len(parts), 3)
        # Altitude = 25000 // 1000 = 25 → "250"
        self.assertIn("25", parts[2])

    def test_zero_alt(self):
        s = bullseye_str(37.0, 127.0, 38.0, 128.0, 0)
        self.assertIn("000", s)


class TestBmsToLatlon(unittest.TestCase):
    def test_returns_valid_korea(self):
        """BMS TMERC coords should convert to Korean peninsula area."""
        lat, lon = bms_to_latlon(1746000, 1571000)
        self.assertTrue(33 <= lat <= 43, f"Lat {lat} outside Korea range")
        self.assertTrue(124 <= lon <= 132, f"Lon {lon} outside Korea range")

    def test_returns_tuple(self):
        result = bms_to_latlon(1700000, 1500000)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_valid_coordinates(self):
        lat, lon = bms_to_latlon(1700000, 1500000)
        self.assertTrue(-90 <= lat <= 90)
        self.assertTrue(-180 <= lon <= 180)

    def test_different_inputs_different_outputs(self):
        a = bms_to_latlon(1700000, 1500000)
        b = bms_to_latlon(1800000, 1600000)
        self.assertNotEqual(a, b)


class TestStaticData(unittest.TestCase):
    def test_airports_not_empty(self):
        self.assertGreater(len(AIRPORTS), 30)

    def test_airport_structure(self):
        for icao, apt in AIRPORTS.items():
            self.assertIn("lat", apt, f"Missing lat in {icao}")
            self.assertIn("lon", apt, f"Missing lon in {icao}")
            self.assertIn("name", apt, f"Missing name in {icao}")
            self.assertTrue(-90 <= apt["lat"] <= 90, f"Bad lat in {icao}")
            self.assertTrue(100 <= apt["lon"] <= 180, f"Bad lon in {icao}")

    def test_coastline_valid(self):
        self.assertGreater(len(COASTLINE_KOREA), 50)
        for lat, lon in COASTLINE_KOREA:
            self.assertTrue(30 <= lat <= 50, f"Bad coastline lat: {lat}")
            self.assertTrue(120 <= lon <= 135, f"Bad coastline lon: {lon}")

    def test_dmz_valid(self):
        self.assertGreater(len(DMZ_LINE), 10)
        for lat, lon in DMZ_LINE:
            self.assertAlmostEqual(lat, 38.0, delta=1.0)

    def test_runway_polygons_valid(self):
        self.assertGreater(len(RUNWAY_POLYGONS), 10)
        for icao, polys in RUNWAY_POLYGONS.items():
            self.assertIn(icao, AIRPORTS, f"Runway {icao} not in AIRPORTS")
            for corners in polys:
                self.assertEqual(len(corners), 4, f"Bad polygon for {icao}")


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS : core/trtt_client.py
# ═══════════════════════════════════════════════════════════════════════════════
from core.trtt_client import (Track, TRTTClient, ID_UNKNOWN, ID_FRIEND,
                               ID_BOGEY, ID_BANDIT, ID_HOSTILE, ID_NEUTRAL,
                               ID_COLORS, COLOR_PRESETS, _coalition_color)


class TestTrack(unittest.TestCase):
    def test_defaults(self):
        t = Track(uid="A001")
        self.assertEqual(t.uid, "A001")
        self.assertEqual(t.lat, 0.0)
        self.assertEqual(t.id_code, ID_UNKNOWN)
        self.assertTrue(t.alive)
        self.assertFalse(t.is_human)

    def test_alt_ft_conversion(self):
        t = Track(uid="A002", alt=10000.0)
        self.assertAlmostEqual(t.alt_ft, 32808, delta=2)

    def test_speed_kts_conversion(self):
        t = Track(uid="A003", speed=200.0)  # 200 m/s
        self.assertAlmostEqual(t.speed_kts, 388, delta=2)

    def test_is_air(self):
        t = Track(uid="A004", obj_type="Air+FixedWing")
        self.assertTrue(t.is_air)
        self.assertFalse(t.is_missile)
        self.assertFalse(t.is_ground)

    def test_is_missile(self):
        t = Track(uid="A005", obj_type="Weapon+Missile")
        self.assertTrue(t.is_missile)
        self.assertFalse(t.is_air)

    def test_is_ground(self):
        t = Track(uid="A006", obj_type="Ground+Vehicle")
        self.assertTrue(t.is_ground)

    def test_is_rotary(self):
        t = Track(uid="A007", obj_type="Air+Rotorcraft")
        self.assertTrue(t.is_rotary)
        self.assertTrue(t.is_air)

    def test_display_label_callsign(self):
        t = Track(uid="A008", callsign="Viper11", pilot="PlayerX", name="F-16CM")
        self.assertEqual(t.display_label, "Viper11")

    def test_display_label_pilot_fallback(self):
        t = Track(uid="A009", pilot="PlayerX", name="F-16CM")
        self.assertEqual(t.display_label, "PlayerX")

    def test_display_label_name_fallback(self):
        t = Track(uid="A010", name="F-16CM-52")
        self.assertEqual(t.display_label, "F-16CM-5")

    def test_display_label_uid_fallback(self):
        t = Track(uid="ABC123")
        self.assertEqual(t.display_label, "ABC123")

    def test_color_custom(self):
        t = Track(uid="A011", custom_color="#ff00ff")
        self.assertEqual(t.color, "#ff00ff")

    def test_color_id_code(self):
        t = Track(uid="A012", id_code=ID_FRIEND)
        self.assertEqual(t.color, ID_COLORS[ID_FRIEND])

    def test_color_coalition_fallback(self):
        t = Track(uid="A013", coalition="Blue")
        self.assertEqual(t.color, ID_COLORS[ID_UNKNOWN])

    def test_push_trail(self):
        t = Track(uid="A014", lat=37.0, lon=127.0)
        t.push_trail()
        self.assertEqual(len(t.trail), 1)
        t.lat = 37.1; t.lon = 127.1
        t.push_trail()
        self.assertEqual(len(t.trail), 2)

    def test_push_trail_no_duplicate(self):
        t = Track(uid="A015", lat=37.0, lon=127.0)
        t.push_trail()
        t.push_trail()  # Same position
        self.assertEqual(len(t.trail), 1)

    def test_push_trail_max_length(self):
        t = Track(uid="A016", TRAIL_MAX=5)
        for i in range(20):
            t.lat = 37.0 + i * 0.01
            t.lon = 127.0
            t.push_trail()
        self.assertEqual(len(t.trail), 5)

    def test_to_dict(self):
        t = Track(uid="A017", lat=37.5, lon=127.0, name="F-16CM",
                  coalition="Blue", id_code=ID_FRIEND)
        d = t.to_dict()
        self.assertEqual(d["uid"], "A017")
        self.assertEqual(d["lat"], 37.5)
        self.assertEqual(d["coalition"], "Blue")
        self.assertIn("alt_ft", d)
        self.assertIn("speed_kts", d)
        self.assertIn("color", d)


class TestCoalitionColor(unittest.TestCase):
    def test_blue(self):
        self.assertEqual(_coalition_color("Blue"), "#22ff44")
        self.assertEqual(_coalition_color("Allies"), "#22ff44")

    def test_red(self):
        self.assertEqual(_coalition_color("Red"), "#ff2222")
        self.assertEqual(_coalition_color("Enemies"), "#ff2222")

    def test_unknown(self):
        self.assertEqual(_coalition_color("Neutral"), "#888888")
        self.assertEqual(_coalition_color(""), "#888888")


class TestColorPresets(unittest.TestCase):
    def test_all_presets_valid(self):
        for num, (color, id_code) in COLOR_PRESETS.items():
            self.assertTrue(color.startswith("#"))
            self.assertIn(id_code, ID_COLORS)


class TestTRTTClientSplitProps(unittest.TestCase):
    """Test the critical _split_props method that parses ACMI lines."""

    def test_simple_props(self):
        kv = TRTTClient._split_props("Name=F-16CM,Coalition=Blue,Country=us")
        self.assertEqual(kv["Name"], "F-16CM")
        self.assertEqual(kv["Coalition"], "Blue")
        self.assertEqual(kv["Country"], "us")

    def test_T_field_with_pipes(self):
        kv = TRTTClient._split_props(
            "T=1.23|4.56|7890|||180.5,Name=F-16CM,Coalition=Blue")
        self.assertIn("T", kv)
        self.assertIn("|", kv["T"])
        self.assertEqual(kv["Name"], "F-16CM")
        self.assertEqual(kv["Coalition"], "Blue")

    def test_T_field_only(self):
        kv = TRTTClient._split_props("T=0.5|1.2|3000|||90")
        self.assertIn("T", kv)
        self.assertIn("|", kv["T"])

    def test_T_field_with_empty_pipes(self):
        kv = TRTTClient._split_props(
            "T=|||||||,Name=MiG-29,Type=Air+FixedWing")
        self.assertIn("T", kv)
        self.assertEqual(kv["Name"], "MiG-29")
        self.assertEqual(kv["Type"], "Air+FixedWing")

    def test_empty_string(self):
        kv = TRTTClient._split_props("")
        self.assertEqual(kv, {})

    def test_no_T_field(self):
        kv = TRTTClient._split_props("Name=F-16CM,Pilot=PlayerX")
        self.assertEqual(kv["Name"], "F-16CM")
        self.assertEqual(kv["Pilot"], "PlayerX")
        self.assertNotIn("T", kv)

    def test_all_acmi_fields(self):
        """Simulate a realistic ACMI line with all fields."""
        line = ("T=0.1234|0.5678|9000|||270.5,Name=F-16CM-52,"
                "Pilot=Viper11,Callsign=Viper11,Group=Package1,"
                "Type=Air+FixedWing,Coalition=Blue,Country=us,"
                "Color=Blue,IAS=250")
        kv = TRTTClient._split_props(line)
        self.assertEqual(kv["Name"], "F-16CM-52")
        self.assertEqual(kv["Pilot"], "Viper11")
        self.assertEqual(kv["Callsign"], "Viper11")
        self.assertEqual(kv["Group"], "Package1")
        self.assertEqual(kv["Type"], "Air+FixedWing")
        self.assertEqual(kv["Coalition"], "Blue")
        self.assertEqual(kv["IAS"], "250")
        self.assertIn("T", kv)


class TestTRTTClientParseTrack(unittest.TestCase):
    def setUp(self):
        self.client = TRTTClient()
        self.client._ref_lat = 0.0
        self.client._ref_lon = 0.0

    def test_new_track_created(self):
        changed = self.client._parse_track(
            "A001", "T=127.0|37.0|5000|||180,Name=F-16CM,Coalition=Blue,Type=Air+FixedWing")
        self.assertTrue(changed)
        self.assertIn("A001", self.client.tracks)
        t = self.client.tracks["A001"]
        self.assertAlmostEqual(t.lat, 37.0, places=1)
        self.assertAlmostEqual(t.lon, 127.0, places=1)
        self.assertEqual(t.name, "F-16CM")
        self.assertEqual(t.coalition, "Blue")

    def test_track_update(self):
        self.client._parse_track(
            "A002", "T=127.0|37.0|5000|||180,Name=F-16CM,Coalition=Blue,Type=Air+FixedWing")
        self.client._parse_track(
            "A002", "T=127.1|37.1|6000|||190")
        t = self.client.tracks["A002"]
        self.assertAlmostEqual(t.lat, 37.1, places=1)
        self.assertAlmostEqual(t.lon, 127.1, places=1)
        self.assertAlmostEqual(t.alt, 6000, places=0)

    def test_coalition_sets_id_code(self):
        self.client._parse_track(
            "B001", "T=127|37|5000|||0,Type=Air+FixedWing,Coalition=Blue")
        self.assertEqual(self.client.tracks["B001"].id_code, ID_FRIEND)

    def test_red_coalition_sets_bogey(self):
        self.client._parse_track(
            "R001", "T=127|37|5000|||0,Type=Air+FixedWing,Coalition=Red")
        self.assertEqual(self.client.tracks["R001"].id_code, ID_BOGEY)

    def test_color_blue_sets_friendly(self):
        """Color=Blue should set coalition to Blue and id_code to FRIENDLY."""
        self.client._parse_track(
            "C001", "T=127|37|5000|||0,Type=Air+FixedWing,Color=Blue")
        t = self.client.tracks["C001"]
        self.assertEqual(t.coalition, "Blue")
        self.assertEqual(t.id_code, ID_FRIEND)

    def test_color_red_sets_hostile(self):
        """Color=Red should set coalition to Red and id_code to BOGEY."""
        self.client._parse_track(
            "C002", "T=127|37|5000|||0,Type=Air+FixedWing,Color=Red")
        t = self.client.tracks["C002"]
        self.assertEqual(t.coalition, "Red")
        self.assertEqual(t.id_code, ID_BOGEY)

    def test_color_overrides_neutral_default(self):
        """Color should override the default Neutral coalition."""
        self.client._parse_track(
            "C003", "T=127|37|5000|||0,Color=Red,Name=MiG-29")
        t = self.client.tracks["C003"]
        self.assertEqual(t.coalition, "Red")

    def test_color_primary_over_coalition(self):
        """If both Color and Coalition present, Color should win."""
        self.client._parse_track(
            "C004", "T=127|37|5000|||0,Color=Red,Coalition=Allies,Type=Air+FixedWing")
        t = self.client.tracks["C004"]
        self.assertEqual(t.coalition, "Red")
        self.assertEqual(t.id_code, ID_BOGEY)

    def test_pilot_sets_human(self):
        self.client._parse_track(
            "H001", "T=127|37|5000|||0,Pilot=PlayerX,Coalition=Blue,Type=Air+FixedWing")
        t = self.client.tracks["H001"]
        self.assertTrue(t.is_human)
        self.assertEqual(t.pilot, "PlayerX")
        self.assertEqual(t.callsign, "PlayerX")  # fallback

    def test_callsign_priority_over_pilot(self):
        self.client._parse_track(
            "H002", "T=127|37|5000|||0,Callsign=Viper11,Pilot=PlayerX,Type=Air+FixedWing")
        t = self.client.tracks["H002"]
        self.assertEqual(t.callsign, "Viper11")
        self.assertEqual(t.pilot, "PlayerX")

    def test_ias_parsing(self):
        self.client._parse_track("S001", "T=127|37|5000|||0,IAS=300")
        t = self.client.tracks["S001"]
        self.assertAlmostEqual(t.speed, 300.0 * 0.514444, places=1)

    def test_reference_offset(self):
        self.client._ref_lat = 37.0
        self.client._ref_lon = 127.0
        self.client._parse_track("O001", "T=0.5|0.3|5000|||0")
        t = self.client.tracks["O001"]
        self.assertAlmostEqual(t.lat, 37.3, places=1)
        self.assertAlmostEqual(t.lon, 127.5, places=1)


class TestTRTTClientParseLine(unittest.TestCase):
    def setUp(self):
        self.client = TRTTClient()

    def test_timestamp_line(self):
        result = self.client._parse_line("#12.345")
        self.assertFalse(result)
        self.assertAlmostEqual(self.client._last_ts, 12.345)

    def test_global_line(self):
        self.client._parse_line("0,ReferenceLatitude=37.0,ReferenceLongitude=127.0")
        self.assertAlmostEqual(self.client._ref_lat, 37.0)
        self.assertAlmostEqual(self.client._ref_lon, 127.0)

    def test_remove_line(self):
        self.client.tracks["X001"] = Track(uid="X001", alive=True)
        result = self.client._parse_line("-X001")
        self.assertTrue(result)
        self.assertFalse(self.client.tracks["X001"].alive)

    def test_track_line(self):
        result = self.client._parse_line(
            "A001,T=127|37|5000|||0,Name=F-16CM,Coalition=Blue,Type=Air+FixedWing")
        self.assertTrue(result)
        self.assertIn("A001", self.client.tracks)


class TestTRTTClientIdManagement(unittest.TestCase):
    def setUp(self):
        self.updates = []
        self.client = TRTTClient(on_update=lambda t: self.updates.append(t))
        self.client.tracks["A001"] = Track(uid="A001", id_code=ID_UNKNOWN)

    def test_set_track_id(self):
        self.client.set_track_id("A001", ID_HOSTILE, "#ff0000")
        self.assertEqual(self.client.tracks["A001"].id_code, ID_HOSTILE)
        self.assertEqual(self.client.tracks["A001"].custom_color, "#ff0000")
        self.assertEqual(len(self.updates), 1)

    def test_set_track_id_nonexistent(self):
        self.client.set_track_id("NOPE", ID_HOSTILE)
        self.assertEqual(len(self.updates), 0)

    def test_apply_preset(self):
        self.client.apply_preset("A001", 2)  # BANDIT preset
        self.assertEqual(self.client.tracks["A001"].id_code, ID_BANDIT)
        self.assertEqual(self.client.tracks["A001"].custom_color, "#ff2222")

    def test_apply_preset_invalid(self):
        self.client.apply_preset("A001", 99)
        self.assertEqual(self.client.tracks["A001"].id_code, ID_UNKNOWN)

    def test_stats(self):
        self.client.tracks["B001"] = Track(
            uid="B001", alive=True, obj_type="Air+FixedWing", is_human=True)
        self.client.tracks["B002"] = Track(
            uid="B002", alive=True, obj_type="Weapon+Missile")
        self.client.tracks["B003"] = Track(
            uid="B003", alive=False, obj_type="Air+FixedWing")
        stats = self.client.stats()
        self.assertEqual(stats["total"], 4)
        self.assertEqual(stats["alive"], 3)  # A001 + B001 + B002
        self.assertEqual(stats["air"], 1)    # B001
        self.assertEqual(stats["missile"], 1)
        self.assertEqual(stats["human"], 1)


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS : core/mission_parser.py
# ═══════════════════════════════════════════════════════════════════════════════
from core.mission_parser import parse_mission_ini, _parse_entry


class TestParseEntry(unittest.TestCase):
    def test_xyz_only(self):
        result = _parse_entry("1700000, 1500000, 25000")
        self.assertIsNotNone(result)
        x, y, z, radius, name = result
        self.assertEqual(x, 1700000)
        self.assertEqual(y, 1500000)
        self.assertEqual(z, 25000)
        self.assertEqual(radius, 0.0)
        self.assertEqual(name, "")

    def test_xyz_radius_name(self):
        result = _parse_entry("1700000, 1500000, 0, 200000, SA-6")
        x, y, z, radius, name = result
        self.assertEqual(radius, 200000)
        self.assertEqual(name, "SA-6")

    def test_zero_coords_rejected(self):
        result = _parse_entry("0, 0, 0")
        self.assertIsNone(result)

    def test_too_few_parts(self):
        result = _parse_entry("1700000, 1500000")
        self.assertIsNone(result)

    def test_invalid_numbers(self):
        result = _parse_entry("abc, def, ghi")
        self.assertIsNone(result)


class TestParseMissionIni(unittest.TestCase):
    SAMPLE_INI = """\
[STPT]
target_0 = 1746000, 1571000, 25000
target_1 = 1750000, 1575000, 20000
target_2 = 1755000, 1580000, 15000
ppt_0 = 1730000, 1560000, 0, 150000, SA-6
ppt_1 = 1720000, 1550000, 0, 100000, SA-2
ppt_2 = 1342945, 1291184, 0, 0.1, IP1
lineSTPT_0 = 1740000, 1565000, 0
lineSTPT_1 = 1745000, 1570000, 0
lineSTPT_2 = 0, 0, 0
lineSTPT_3 = 1750000, 1575000, 0
lineSTPT_4 = 1755000, 1580000, 0
"""

    def test_parse_basic(self):
        result = parse_mission_ini(self.SAMPLE_INI)
        self.assertIn("bullseye", result)
        self.assertIn("route", result)
        self.assertIn("threats", result)
        self.assertIn("ref_points", result)
        self.assertIn("line_segments", result)

    def test_route_extracted(self):
        result = parse_mission_ini(self.SAMPLE_INI)
        self.assertEqual(len(result["route"]), 3)
        for wp in result["route"]:
            self.assertIn("lat", wp)
            self.assertIn("lon", wp)

    def test_threats_only_real_sam(self):
        """Only PPTs with range > 500m should be in threats."""
        result = parse_mission_ini(self.SAMPLE_INI)
        self.assertEqual(len(result["threats"]), 2)
        for th in result["threats"]:
            self.assertIn("name", th)
            self.assertIn("range_nm", th)
            self.assertIn("range_m", th)
            self.assertGreater(th["range_m"], 500)

    def test_ref_points_for_nav(self):
        """PPTs with tiny range (IPs, nav points) go to ref_points."""
        result = parse_mission_ini(self.SAMPLE_INI)
        self.assertEqual(len(result["ref_points"]), 1)
        self.assertEqual(result["ref_points"][0]["name"], "IP1")

    def test_bullseye_from_first_wp(self):
        result = parse_mission_ini(self.SAMPLE_INI)
        self.assertIsNotNone(result["bullseye"])
        self.assertIn("lat", result["bullseye"])
        self.assertIn("lon", result["bullseye"])

    def test_line_segments_split(self):
        result = parse_mission_ini(self.SAMPLE_INI)
        segments = result["line_segments"]
        self.assertEqual(len(segments), 2)  # Split by 0,0,0

    def test_empty_content(self):
        result = parse_mission_ini("")
        self.assertIsNone(result["bullseye"])
        self.assertEqual(len(result["route"]), 0)

    def test_no_stpt_section(self):
        result = parse_mission_ini("[OTHER]\nkey = value\n")
        self.assertIsNone(result["bullseye"])

    def test_target_index_above_79_ignored(self):
        ini = "[STPT]\ntarget_80 = 1746000, 1571000, 25000\n"
        result = parse_mission_ini(ini)
        self.assertEqual(len(result["route"]), 0)

    def test_bullseye_key(self):
        ini = "[STPT]\nbull_0 = 1746000, 1571000, 0\ntarget_0 = 1750000, 1575000, 25000\n"
        result = parse_mission_ini(ini)
        self.assertIsNotNone(result["bullseye"])
        # bullseye should come from the bull_ key, not the first target
        # (They might have different coordinates)

    def test_comments_ignored(self):
        ini = "[STPT]\n; This is a comment\ntarget_0 = 1746000, 1571000, 25000\n"
        result = parse_mission_ini(ini)
        self.assertEqual(len(result["route"]), 1)

    def test_windows_line_endings(self):
        ini = "[STPT]\r\ntarget_0 = 1746000, 1571000, 25000\r\n"
        result = parse_mission_ini(ini)
        self.assertEqual(len(result["route"]), 1)

    def test_real_ini_nav_vs_sam(self):
        """Real BMS INI: PPTs with range=0.1 are nav points, not SAMs."""
        ini = """[STPT]
target_0=1162752.875, 1539950.625, -42.0, 1, Not set
ppt_0=1490735.25, 1228185.375, 0, 164055.125, SA2
ppt_1=1342945.125, 1291184.125, 0, 0.1, IP1
ppt_2=1622549.125, 1024520.5625, 0, 72913.390625, SA3
ppt_4=1720543.875, 1664447.75, 0, 0.1, R21
"""
        result = parse_mission_ini(ini)
        # SA2 + SA3 = 2 real threats
        self.assertEqual(len(result["threats"]), 2)
        for th in result["threats"]:
            self.assertGreater(th["range_m"], 500)
        # IP1 + R21 = 2 ref points
        self.assertEqual(len(result["ref_points"]), 2)
        names = [r["name"] for r in result["ref_points"]]
        self.assertIn("IP1", names)
        self.assertIn("R21", names)


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS : core/ivc_client.py
# ═══════════════════════════════════════════════════════════════════════════════
from core.ivc_client import IVCClient


class TestIVCNameToFreq(unittest.TestCase):
    def test_freq_in_name(self):
        self.assertEqual(IVCClient._name_to_freq("GCI 234.500 MHz"), "234.500")

    def test_no_freq(self):
        self.assertEqual(IVCClient._name_to_freq("General Chat"), "")

    def test_multiple_numbers(self):
        result = IVCClient._name_to_freq("Channel 127.900 TWR freq")
        self.assertEqual(result, "127.900")


class TestIVCParseTs3(unittest.TestCase):
    def test_parse(self):
        ivc = IVCClient()
        raw = "clid=1 cid=5 client_nickname=TestUser\\sName"
        result = ivc._parse_ts3(raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["clid"], "1")
        self.assertEqual(result[0]["client_nickname"], "TestUser Name")

    def test_pipe_separated(self):
        ivc = IVCClient()
        raw = "clid=1 cid=5|clid=2 cid=6"
        result = ivc._parse_ts3(raw)
        self.assertEqual(len(result), 2)


# ═══════════════════════════════════════════════════════════════════════════════
# Run
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestDetectCamp(unittest.TestCase):
    """Test aircraft-type based camp detection (F4Radar/OpenRadar method)."""

    def test_blue_f16(self):
        from core.trtt_client import _detect_camp
        self.assertEqual(_detect_camp("F-16CM-52", ""), "Blue")

    def test_blue_f15(self):
        from core.trtt_client import _detect_camp
        self.assertEqual(_detect_camp("F-15E", ""), "Blue")

    def test_red_mig29(self):
        from core.trtt_client import _detect_camp
        self.assertEqual(_detect_camp("MiG-29G", ""), "Red")

    def test_red_su27(self):
        from core.trtt_client import _detect_camp
        self.assertEqual(_detect_camp("Su-27SK", ""), "Red")

    def test_red_mig21(self):
        from core.trtt_client import _detect_camp
        self.assertEqual(_detect_camp("MiG-21bis", ""), "Red")

    def test_blue_a10(self):
        from core.trtt_client import _detect_camp
        self.assertEqual(_detect_camp("A-10A", ""), "Blue")

    def test_unknown_truck(self):
        from core.trtt_client import _detect_camp
        self.assertEqual(_detect_camp("KrAZ-255", ""), "")

    def test_country_us(self):
        from core.trtt_client import _detect_camp
        self.assertEqual(_detect_camp("Unknown", "us"), "Blue")

    def test_country_kp(self):
        from core.trtt_client import _detect_camp
        self.assertEqual(_detect_camp("Unknown", "kp"), "Red")

    def test_country_kr(self):
        from core.trtt_client import _detect_camp
        self.assertEqual(_detect_camp("Unknown", "kr"), "Blue")
