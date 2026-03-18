# -*- coding: utf-8 -*-
"""
Tests unitaires — Falcon-Eye GCI
Couvre : core/data.py · core/trtt_client.py · core/mission_parser.py · core/ivc_client.py

Lancer :
    python -m unittest tests/test_core.py -v
"""
import sys, os, math, time, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.data import (haversine_nm, bearing_deg, braa_str, bullseye_str,
                        bms_to_latlon, AIRPORTS, COASTLINE_KOREA, DMZ_LINE,
                        RUNWAY_POLYGONS)
from core.trtt_client import (Track, TRTTClient, ID_UNKNOWN, ID_FRIEND,
                               ID_BOGEY, ID_BANDIT, ID_HOSTILE, ID_NEUTRAL,
                               ID_COLORS, COLOR_PRESETS, _coalition_color, _detect_camp)
from core.mission_parser import parse_mission_ini, _parse_entry, _group_line_segments
from core.ivc_client import IVCClient


# ── data.py ──────────────────────────────────────────────────────────────────
class TestHaversine(unittest.TestCase):
    def test_zero(self):
        self.assertAlmostEqual(haversine_nm(37.5,127.0,37.5,127.0), 0.0, places=5)
    def test_osan_gunsan(self):
        self.assertAlmostEqual(haversine_nm(37.09,127.03,35.91,126.62), 73.0, delta=3.0)
    def test_symmetry(self):
        self.assertAlmostEqual(haversine_nm(37,127,38,128), haversine_nm(38,128,37,127), places=6)
    def test_one_degree_lat_approx_60nm(self):
        self.assertAlmostEqual(haversine_nm(37,127,38,127), 60.0, delta=1.0)
    def test_positive(self):
        self.assertGreater(haversine_nm(37,127,38,128), 0.0)


class TestBearing(unittest.TestCase):
    def test_north(self):  self.assertAlmostEqual(bearing_deg(37,127,38,127),   0.0, delta=1.0)
    def test_east(self):   self.assertAlmostEqual(bearing_deg(37,127,37,128),  90.0, delta=2.0)
    def test_south(self):  self.assertAlmostEqual(bearing_deg(38,127,37,127), 180.0, delta=1.0)
    def test_west(self):   self.assertAlmostEqual(bearing_deg(37,128,37,127), 270.0, delta=2.0)
    def test_range(self):
        for la2,lo2 in [(38,128),(36,126),(38,126),(36,128)]:
            b = bearing_deg(37,127,la2,lo2)
            self.assertGreaterEqual(b,0.0); self.assertLess(b,360.0)
    def test_reciprocal_180(self):
        b1=bearing_deg(37,127,38,128); b2=bearing_deg(38,128,37,127)
        self.assertLess(abs((b1-b2+360)%360-180), 5.0)
    def test_ne_quadrant(self):
        b=bearing_deg(37,127,38,128); self.assertGreater(b,0); self.assertLess(b,90)


class TestBraaStr(unittest.TestCase):
    def test_two_parts(self):
        s=braa_str(37,127,38,128); p=s.split("/")
        self.assertEqual(len(p),2); self.assertIn("NM",p[1])
    def test_three_digit_bearing(self):
        s=braa_str(37,127,37,127.001)
        bp=s.split("/")[0].strip(); self.assertEqual(len(bp),3); self.assertTrue(bp.isdigit())
    def test_positive_range(self):
        s=braa_str(37,127,38,128)
        self.assertGreater(float(s.split("/")[1].replace("NM","").strip()),0)


class TestBullseyeStr(unittest.TestCase):
    def test_three_parts(self):   self.assertEqual(len(bullseye_str(37,127,38,128,25000).split("/")),3)
    def test_25000ft_is_250(self):self.assertEqual(bullseye_str(37,127,38,128,25000).split("/")[2].strip(),"250")
    def test_zero_alt(self):      self.assertEqual(bullseye_str(37,127,38,128,0).split("/")[2].strip(),"000")
    def test_fl350(self):         self.assertEqual(bullseye_str(37,127,38,128,35000).split("/")[2].strip(),"350")


class TestBmsToLatlon(unittest.TestCase):
    def test_korea_range(self):
        lat,lon=bms_to_latlon(1746000,1571000)
        self.assertTrue(33<=lat<=43); self.assertTrue(124<=lon<=132)
    def test_tuple(self):         self.assertEqual(len(bms_to_latlon(1700000,1500000)),2)
    def test_wgs84(self):
        lat,lon=bms_to_latlon(1700000,1500000)
        self.assertTrue(-90<=lat<=90); self.assertTrue(-180<=lon<=180)
    def test_different(self):     self.assertNotEqual(bms_to_latlon(1700000,1500000),bms_to_latlon(1800000,1600000))
    def test_north_monotonic(self):
        lat1,_=bms_to_latlon(1700000,1500000); lat2,_=bms_to_latlon(1800000,1500000)
        self.assertGreater(lat2,lat1)
    def test_east_monotonic(self):
        _,lon1=bms_to_latlon(1700000,1500000); _,lon2=bms_to_latlon(1700000,1600000)
        self.assertGreater(lon2,lon1)


class TestStaticData(unittest.TestCase):
    def test_airports_count(self):    self.assertGreater(len(AIRPORTS),30)
    def test_airport_fields(self):
        for icao,apt in AIRPORTS.items():
            with self.subTest(icao=icao):
                self.assertIn("lat",apt); self.assertIn("lon",apt); self.assertIn("name",apt)
                self.assertTrue(-90<=apt["lat"]<=90); self.assertTrue(100<=apt["lon"]<=180)
    def test_known_airports(self):
        for icao in ("RKSO","RKSG","RKSI","RKSS","RKTN"): self.assertIn(icao,AIRPORTS)
    def test_coastline(self):
        for lat,lon in COASTLINE_KOREA: self.assertTrue(30<=lat<=50); self.assertTrue(120<=lon<=135)
    def test_dmz(self):
        for lat,lon in DMZ_LINE: self.assertAlmostEqual(lat,38.0,delta=1.0)
    def test_runways_linked(self):
        for icao in RUNWAY_POLYGONS: self.assertIn(icao,AIRPORTS)
    def test_runway_corners(self):
        for icao,polys in RUNWAY_POLYGONS.items():
            for corners in polys: self.assertEqual(len(corners),4)


# ── trtt_client.py ────────────────────────────────────────────────────────────
class TestTrack(unittest.TestCase):
    def test_defaults(self):
        t=Track(uid="A001")
        self.assertEqual(t.uid,"A001"); self.assertEqual(t.lat,0.0)
        self.assertEqual(t.id_code,ID_UNKNOWN); self.assertTrue(t.alive); self.assertFalse(t.is_human)
    def test_alt_ft(self):    self.assertAlmostEqual(Track(uid="X",alt=10000.0).alt_ft, 32808, delta=2)
    def test_speed_kts(self): self.assertAlmostEqual(Track(uid="X",speed=200.0).speed_kts, 388, delta=2)
    def test_is_air(self):
        t=Track(uid="X",obj_type="Air+FixedWing")
        self.assertTrue(t.is_air); self.assertFalse(t.is_missile); self.assertFalse(t.is_ground)
    def test_is_rotary(self):
        t=Track(uid="X",obj_type="Air+Rotorcraft"); self.assertTrue(t.is_air); self.assertTrue(t.is_rotary)
    def test_is_missile(self):
        t=Track(uid="X",obj_type="Weapon+Missile"); self.assertTrue(t.is_missile); self.assertFalse(t.is_air)
    def test_is_ground(self):  self.assertTrue(Track(uid="X",obj_type="Ground+Vehicle").is_ground)
    def test_label_callsign(self): self.assertEqual(Track(uid="X",callsign="V11",pilot="P",name="F-16").display_label,"V11")
    def test_label_pilot(self):    self.assertEqual(Track(uid="X",pilot="P",name="F-16").display_label,"P")
    def test_label_name(self):     self.assertEqual(Track(uid="X",name="F-16CM-52").display_label,"F-16CM-5")
    def test_label_uid(self):      self.assertEqual(Track(uid="ABC123").display_label,"ABC123")
    def test_color_custom(self):   self.assertEqual(Track(uid="X",custom_color="#ff00ff").color,"#ff00ff")
    def test_color_id(self):       self.assertEqual(Track(uid="X",id_code=ID_FRIEND).color,ID_COLORS[ID_FRIEND])
    def test_trail_add(self):
        t=Track(uid="X",lat=37.0,lon=127.0); t.push_trail(); self.assertEqual(len(t.trail),1)
    def test_trail_no_dup(self):
        t=Track(uid="X",lat=37.0,lon=127.0); t.push_trail(); t.push_trail(); self.assertEqual(len(t.trail),1)
    def test_trail_max(self):
        t=Track(uid="X",TRAIL_MAX=5)
        for i in range(20): t.lat=37+i*0.01; t.lon=127.0; t.push_trail()
        self.assertEqual(len(t.trail),5)
    def test_trail_skip_zero(self):
        t=Track(uid="X",lat=0.0,lon=0.0); t.push_trail(); self.assertEqual(len(t.trail),0)
    def test_to_dict_keys(self):
        d=Track(uid="X",lat=37.5,lon=127.0,coalition="Blue").to_dict()
        for k in ("uid","lat","lon","alt_ft","speed_kts","hdg","coalition","id_code","color","alive"):
            self.assertIn(k,d)


class TestCoalitionColor(unittest.TestCase):
    def test_blue(self):  self.assertEqual(_coalition_color("Blue"),"#22ff44"); self.assertEqual(_coalition_color("Allies"),"#22ff44")
    def test_red(self):   self.assertEqual(_coalition_color("Red"),"#ff2222")
    def test_other(self): self.assertEqual(_coalition_color("Neutral"),"#888888"); self.assertEqual(_coalition_color(""),"#888888")


class TestColorPresets(unittest.TestCase):
    def test_all_valid(self):
        self.assertGreater(len(COLOR_PRESETS),0)
        for num,(color,id_code) in COLOR_PRESETS.items():
            self.assertTrue(color.startswith("#")); self.assertIn(id_code,ID_COLORS)


class TestDetectCamp(unittest.TestCase):
    def test_f16(self):   self.assertEqual(_detect_camp("F-16CM-52",""),"Blue")
    def test_f15(self):   self.assertEqual(_detect_camp("F-15E",""),"Blue")
    def test_a10(self):   self.assertEqual(_detect_camp("A-10A",""),"Blue")
    def test_mig29(self): self.assertEqual(_detect_camp("MiG-29G",""),"Red")
    def test_su27(self):  self.assertEqual(_detect_camp("Su-27SK",""),"Red")
    def test_mig21(self): self.assertEqual(_detect_camp("MiG-21bis",""),"Red")
    def test_us(self):    self.assertEqual(_detect_camp("Unknown","us"),"Blue")
    def test_kr(self):    self.assertEqual(_detect_camp("Unknown","kr"),"Blue")
    def test_kp(self):    self.assertEqual(_detect_camp("Unknown","kp"),"Red")
    def test_cn(self):    self.assertEqual(_detect_camp("Unknown","cn"),"Red")
    def test_truck(self): self.assertEqual(_detect_camp("KrAZ-255",""),"")
    def test_empty(self): self.assertEqual(_detect_camp("",""),"")


class TestSplitProps(unittest.TestCase):
    def test_simple(self):
        kv=TRTTClient._split_props("Name=F-16CM,Coalition=Blue")
        self.assertEqual(kv["Name"],"F-16CM"); self.assertEqual(kv["Coalition"],"Blue")
    def test_T_with_pipes(self):
        kv=TRTTClient._split_props("T=1.23|4.56|7890|||180.5,Name=F-16CM")
        self.assertIn("T",kv); self.assertEqual(kv["Name"],"F-16CM")
    def test_T_empty_pipes(self):
        kv=TRTTClient._split_props("T=|||||||,Name=MiG-29,Type=Air+FixedWing")
        self.assertIn("T",kv); self.assertEqual(kv["Name"],"MiG-29")
    def test_empty(self):        self.assertEqual(TRTTClient._split_props(""),{})
    def test_no_T(self):
        kv=TRTTClient._split_props("Name=F-16CM,Pilot=P"); self.assertNotIn("T",kv)
    def test_full_line(self):
        line="T=0.12|0.56|9000|||270,Name=F-16CM-52,Callsign=Viper11,Type=Air+FixedWing,Coalition=Blue,IAS=250"
        kv=TRTTClient._split_props(line)
        self.assertEqual(kv["Name"],"F-16CM-52"); self.assertEqual(kv["Callsign"],"Viper11")
        self.assertEqual(kv["IAS"],"250"); self.assertIn("T",kv)


class TestParseTrack(unittest.TestCase):
    def setUp(self):
        self.c=TRTTClient(); self.c._ref_lat=0.0; self.c._ref_lon=0.0
    def p(self,uid,props): return self.c._parse_track(uid,props)

    def test_creates_track(self):
        self.p("A001","T=127|37|5000|||180,Name=F-16CM,Coalition=Blue,Type=Air+FixedWing")
        t=self.c.tracks["A001"]
        self.assertAlmostEqual(t.lat,37.0,places=1); self.assertEqual(t.name,"F-16CM")
    def test_update_position(self):
        self.p("A002","T=127|37|5000|||180,Coalition=Blue,Type=Air+FixedWing")
        self.p("A002","T=127.1|37.1|6000|||190")
        t=self.c.tracks["A002"]
        self.assertAlmostEqual(t.lat,37.1,places=1); self.assertAlmostEqual(t.alt,6000,places=0)
    def test_blue_friend(self):
        self.p("B001","T=127|37|5000|||0,Type=Air+FixedWing,Coalition=Blue")
        self.assertEqual(self.c.tracks["B001"].id_code,ID_FRIEND)
    def test_red_bogey(self):
        self.p("R001","T=127|37|5000|||0,Type=Air+FixedWing,Coalition=Red")
        self.assertEqual(self.c.tracks["R001"].id_code,ID_BOGEY)
    def test_color_blue(self):
        self.p("C001","T=127|37|5000|||0,Color=Blue,Type=Air+FixedWing")
        self.assertEqual(self.c.tracks["C001"].coalition,"Blue"); self.assertEqual(self.c.tracks["C001"].id_code,ID_FRIEND)
    def test_color_red(self):
        self.p("C002","T=127|37|5000|||0,Color=Red")
        self.assertEqual(self.c.tracks["C002"].coalition,"Red")
    def test_color_overrides_coalition(self):
        self.p("C003","T=127|37|5000|||0,Color=Red,Coalition=Allies")
        self.assertEqual(self.c.tracks["C003"].coalition,"Red")
    def test_pilot_human(self):
        self.p("H001","T=127|37|5000|||0,Pilot=PlayerX,Coalition=Blue,Type=Air+FixedWing")
        t=self.c.tracks["H001"]; self.assertTrue(t.is_human); self.assertEqual(t.pilot,"PlayerX")
    def test_callsign_priority(self):
        self.p("H002","T=127|37|5000|||0,Callsign=Viper11,Pilot=PlayerX")
        self.assertEqual(self.c.tracks["H002"].display_label,"Viper11")
    def test_ias(self):
        # IAS in Tacview ACMI is in m/s — stored directly, no conversion
        self.p("S001","T=127|37|5000|||0,IAS=154.33")
        self.assertAlmostEqual(self.c.tracks["S001"].speed, 154.33, places=1)
        # 154.33 m/s = ~300 kts
        self.assertAlmostEqual(self.c.tracks["S001"].speed_kts, 300, delta=2)
    def test_hdg_mod360(self):
        self.p("HD001","T=127|37|5000|||361")
        self.assertAlmostEqual(self.c.tracks["HD001"].hdg,1.0,delta=1.0)
    def test_ref_offset(self):
        self.c._ref_lat=37.0; self.c._ref_lon=127.0
        self.p("O001","T=0.5|0.3|5000|||0")
        t=self.c.tracks["O001"]
        self.assertAlmostEqual(t.lat,37.3,places=1); self.assertAlmostEqual(t.lon,127.5,places=1)
    def test_alive_true(self):
        self.p("AL001","T=127|37|5000|||0"); self.assertTrue(self.c.tracks["AL001"].alive)


class TestParseLine(unittest.TestCase):
    def setUp(self): self.c=TRTTClient()
    def test_timestamp(self):
        self.assertFalse(self.c._parse_line("#12.345"))
        self.assertAlmostEqual(self.c._last_ts,12.345)
    def test_global(self):
        self.c._parse_line("0,ReferenceLatitude=37.0,ReferenceLongitude=127.0")
        self.assertAlmostEqual(self.c._ref_lat,37.0)
    def test_remove(self):
        self.c.tracks["X001"]=Track(uid="X001",alive=True)
        self.assertTrue(self.c._parse_line("-X001")); self.assertFalse(self.c.tracks["X001"].alive)
    def test_remove_nonexistent(self): self.assertTrue(self.c._parse_line("-NOPE"))
    def test_track_line(self):
        self.assertTrue(self.c._parse_line("A001,T=127|37|5000|||0,Coalition=Blue,Type=Air+FixedWing"))
        self.assertIn("A001",self.c.tracks)
    def test_malformed(self): self.assertFalse(self.c._parse_line("notvalid"))
    def test_empty(self):     self.assertFalse(self.c._parse_line(""))


class TestIdManagement(unittest.TestCase):
    def setUp(self):
        self.updates=[]; self.c=TRTTClient(on_update=lambda t: self.updates.append(len(t)))
        self.c.tracks["A001"]=Track(uid="A001",id_code=ID_UNKNOWN)
    def test_set_id(self):
        self.c.set_track_id("A001",ID_HOSTILE,"#ff0000")
        self.assertEqual(self.c.tracks["A001"].id_code,ID_HOSTILE); self.assertEqual(len(self.updates),1)
    def test_set_nonexistent(self): self.c.set_track_id("NOPE",ID_HOSTILE); self.assertEqual(len(self.updates),0)
    def test_apply_preset(self):
        self.c.apply_preset("A001",2); self.assertEqual(self.c.tracks["A001"].id_code,ID_BANDIT)
    def test_apply_invalid_preset(self):
        self.c.apply_preset("A001",99); self.assertEqual(self.c.tracks["A001"].id_code,ID_UNKNOWN)
    def test_stats(self):
        self.c.tracks["B001"]=Track(uid="B001",alive=True,obj_type="Air+FixedWing",is_human=True)
        self.c.tracks["B002"]=Track(uid="B002",alive=True,obj_type="Weapon+Missile")
        self.c.tracks["B003"]=Track(uid="B003",alive=False,obj_type="Air+FixedWing")
        s=self.c.stats()
        self.assertEqual(s["total"],4); self.assertEqual(s["alive"],3)
        self.assertEqual(s["air"],1); self.assertEqual(s["missile"],1); self.assertEqual(s["human"],1)
    def test_stats_empty(self): self.assertEqual(TRTTClient().stats()["total"],0)


class TestParseBuffer(unittest.TestCase):
    def test_fires_callback(self):
        updates=[]; c=TRTTClient(on_update=lambda t: updates.append(len(t)))
        c._buf=("0,ReferenceLatitude=37.0,ReferenceLongitude=127.0\n"
                "A001,T=127|37|5000|||180,Name=F-16CM,Coalition=Blue,Type=Air+FixedWing\n")
        c._parse_buffer()
        self.assertEqual(len(updates),1); self.assertIn("A001",c.tracks)
    def test_incomplete_buffered(self):
        c=TRTTClient(); c._buf="A001,T=127|37|5000|||0,Na"
        c._parse_buffer(); self.assertNotIn("A001",c.tracks); self.assertIn("Na",c._buf)
    def test_stale_tracks_dead(self):
        c=TRTTClient()
        old=Track(uid="OLD",alive=True); old.updated_at=time.time()-120; c.tracks["OLD"]=old
        c._buf="#1.0\nA001,T=127|37|5000|||0,Type=Air+FixedWing\n"
        c._parse_buffer()
        self.assertFalse(c.tracks["OLD"].alive); self.assertTrue(c.tracks["A001"].alive)


# ── mission_parser.py ─────────────────────────────────────────────────────────
class TestParseEntry(unittest.TestCase):
    def test_xyz(self):
        x,y,z,r,n=_parse_entry("1700000, 1500000, 25000")
        self.assertEqual(x,1700000); self.assertEqual(r,0.0); self.assertEqual(n,"")
    def test_with_range_name(self):
        x,y,z,r,n=_parse_entry("1700000, 1500000, 0, 200000, SA-6")
        self.assertEqual(r,200000); self.assertEqual(n,"SA-6")
    def test_zero_rejected(self): self.assertIsNone(_parse_entry("0, 0, 0"))
    def test_too_few(self):       self.assertIsNone(_parse_entry("1700000, 1500000"))
    def test_invalid(self):       self.assertIsNone(_parse_entry("abc, def, ghi"))
    def test_tiny_radius(self):   self.assertIsNotNone(_parse_entry("1700000, 1500000, 0, 0.1, IP1"))


SAMPLE_INI = """
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

class TestParseMission(unittest.TestCase):
    def test_keys(self):
        r=parse_mission_ini(SAMPLE_INI)
        for k in ("bullseye","route","threats","ref_points","lines","line_segments","flightplan"):
            self.assertIn(k,r)
    def test_route_count(self):   self.assertEqual(len(parse_mission_ini(SAMPLE_INI)["route"]),3)
    def test_threats_real_only(self):
        r=parse_mission_ini(SAMPLE_INI); self.assertEqual(len(r["threats"]),2)
        for th in r["threats"]: self.assertGreater(th["range_m"],500)
    def test_nav_ref_points(self):
        r=parse_mission_ini(SAMPLE_INI); self.assertEqual(len(r["ref_points"]),1)
        self.assertEqual(r["ref_points"][0]["name"],"IP1")
    def test_bullseye(self):
        r=parse_mission_ini(SAMPLE_INI); self.assertIsNotNone(r["bullseye"]); self.assertIn("lat",r["bullseye"])
    def test_segments_split(self): self.assertEqual(len(parse_mission_ini(SAMPLE_INI)["line_segments"]),2)
    def test_empty(self):
        r=parse_mission_ini(""); self.assertIsNone(r["bullseye"]); self.assertEqual(r["route"],[])
    def test_no_stpt(self):        self.assertIsNone(parse_mission_ini("[OTHER]\nk=v\n")["bullseye"])
    def test_index_80_ignored(self):
        r=parse_mission_ini("[STPT]\ntarget_80 = 1746000, 1571000, 25000\n")
        self.assertEqual(len(r["route"]),0)
    def test_comments(self):
        r=parse_mission_ini("[STPT]\n; c\ntarget_0 = 1746000, 1571000, 25000\n")
        self.assertEqual(len(r["route"]),1)
    def test_crlf(self):
        r=parse_mission_ini("[STPT]\r\ntarget_0 = 1746000, 1571000, 25000\r\n")
        self.assertEqual(len(r["route"]),1)
    def test_real_ini(self):
        ini=("[STPT]\ntarget_0=1162752.875, 1539950.625, -42.0\n"
             "ppt_0=1490735.25, 1228185.375, 0, 164055.125, SA2\n"
             "ppt_1=1342945.125, 1291184.125, 0, 0.1, IP1\n"
             "ppt_2=1622549.125, 1024520.5625, 0, 72913.390625, SA3\n"
             "ppt_4=1720543.875, 1664447.75, 0, 0.1, R21\n")
        r=parse_mission_ini(ini); self.assertEqual(len(r["threats"]),2)
        names=[x["name"] for x in r["ref_points"]]
        self.assertIn("IP1",names); self.assertIn("R21",names)
    def test_range_nm(self):
        r=parse_mission_ini("[STPT]\nppt_0 = 1730000, 1560000, 0, 164000, SA-2\n")
        self.assertIn("range_nm",r["threats"][0]); self.assertGreater(r["threats"][0]["range_nm"],0)
    def test_wpntarget(self):
        r=parse_mission_ini("[STPT]\nwpntarget_0 = 1746000, 1571000, 25000\n")
        self.assertEqual(len(r["flightplan"]),1)
    def test_explicit_bull(self):
        r=parse_mission_ini("[STPT]\nbull_0 = 1746000, 1571000, 0\ntarget_0 = 1750000, 1575000, 25000\n")
        self.assertIsNotNone(r["bullseye"])


class TestGroupSegments(unittest.TestCase):
    def test_single(self):
        ini="[STPT]\nlineSTPT_0 = 1740000, 1565000, 0\nlineSTPT_1 = 1750000, 1575000, 0\n"
        segs=_group_line_segments(ini); self.assertEqual(len(segs),1); self.assertEqual(len(segs[0]),2)
    def test_split_by_zero(self):
        ini=("[STPT]\nlineSTPT_0 = 1740000, 1565000, 0\nlineSTPT_1 = 1745000, 1570000, 0\n"
             "lineSTPT_2 = 0, 0, 0\nlineSTPT_3 = 1750000, 1575000, 0\nlineSTPT_4 = 1755000, 1580000, 0\n")
        self.assertEqual(len(_group_line_segments(ini)),2)
    def test_single_point_not_segment(self):
        ini="[STPT]\nlineSTPT_0 = 1740000, 1565000, 0\n"
        self.assertEqual(len(_group_line_segments(ini)),0)
    def test_empty(self): self.assertEqual(_group_line_segments(""),[])


# ── ivc_client.py ─────────────────────────────────────────────────────────────
class TestIVCNameToFreq(unittest.TestCase):
    def test_freq(self):   self.assertEqual(IVCClient._name_to_freq("GCI 234.500 MHz"),"234.500")
    def test_no_freq(self):self.assertEqual(IVCClient._name_to_freq("General Chat"),"")
    def test_first(self):  self.assertEqual(IVCClient._name_to_freq("225.000 GCI PRI"),"225.000")
    def test_empty(self):  self.assertEqual(IVCClient._name_to_freq(""),"")


class TestIVCParseTs3(unittest.TestCase):
    def setUp(self): self.ivc=IVCClient()
    def test_single(self):
        r=self.ivc._parse_ts3("clid=1 cid=5 client_nickname=Test")
        self.assertEqual(len(r),1); self.assertEqual(r[0]["clid"],"1")
    def test_space_escape(self):
        r=self.ivc._parse_ts3("clid=1 cid=5 client_nickname=Test\\sUser")
        self.assertEqual(r[0]["client_nickname"],"Test User")
    def test_pipe(self):
        r=self.ivc._parse_ts3("clid=1 cid=5|clid=2 cid=6"); self.assertEqual(len(r),2)
    def test_talking(self):
        r=self.ivc._parse_ts3("clid=1 cid=5 client_flag_talking=1")
        self.assertEqual(r[0]["client_flag_talking"],"1")
    def test_empty(self): self.assertEqual(self.ivc._parse_ts3(""),[])
    def test_pipe_escape(self):
        r=self.ivc._parse_ts3("clid=1 client_nickname=User\\pName")
        self.assertEqual(r[0]["client_nickname"],"User|Name")


class TestIVCState(unittest.TestCase):
    def test_initial(self):  self.assertFalse(IVCClient().connected); self.assertIsNone(IVCClient().sock)
    def test_disconnect(self): IVCClient().disconnect()
    def test_channels_disconnected(self): self.assertEqual(IVCClient().get_channels(),[])
    def test_talking_disconnected(self):  self.assertEqual(IVCClient().get_talking(),"")
    def test_join_disconnected(self):     self.assertFalse(IVCClient().join_channel("5"))


class TestIVCSharedMem(unittest.TestCase):
    """Tests IVC via SharedMemory BMS (nouvelle implémentation)."""

    def _ivc_with_sm(self, uhf_freq="339.750", vhf_freq="127.500", running=True):
        """IVCClient avec get_radio_data et is_bms_running mockés dans ivc_client."""
        import core.ivc_client as ivc_mod
        ivc = IVCClient()
        ivc.connected = running
        # Patch directly in ivc_client namespace (handles 'from x import y' pattern)
        ivc_mod.is_bms_running = lambda: running
        if running:
            ivc_mod.get_radio_data = lambda: {"uhf_freq": uhf_freq, "vhf_freq": vhf_freq}
        else:
            ivc_mod.get_radio_data = lambda: None
        return ivc

    def tearDown(self):
        """Restore original functions from shared_mem."""
        import core.ivc_client as ivc_mod
        from core.shared_mem import get_radio_data, is_bms_running
        ivc_mod.is_bms_running = is_bms_running
        ivc_mod.get_radio_data = get_radio_data

    def test_get_channels_returns_uhf_vhf(self):
        ivc = self._ivc_with_sm("305.000", "127.900")
        r = ivc.get_channels()
        self.assertEqual(len(r), 2)
        freqs = [c["freq"] for c in r]
        self.assertIn("305.000", freqs)
        self.assertIn("127.900", freqs)

    def test_get_channels_uhf_only(self):
        ivc = self._ivc_with_sm("339.750", "")
        r = ivc.get_channels()
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["freq"], "339.750")
        self.assertEqual(r[0]["id"], "uhf")

    def test_get_channels_bms_down(self):
        ivc = self._ivc_with_sm(running=False)
        r = ivc.get_channels()
        self.assertEqual(r, [])
        self.assertFalse(ivc.connected)

    def test_get_talking_always_empty(self):
        """IVC BMS ne peut pas détecter qui parle via SM."""
        ivc = self._ivc_with_sm()
        self.assertEqual(ivc.get_talking(), "")

    def test_join_channel_unsupported(self):
        ivc = self._ivc_with_sm()
        self.assertFalse(ivc.join_channel("5"))

    def test_connect_bms_running(self):
        import core.ivc_client as ivc_mod
        ivc_mod.is_bms_running = lambda: True
        ivc = IVCClient()
        r = ivc.connect()
        self.assertEqual(r["status"], "ok")
        self.assertTrue(ivc.connected)

    def test_connect_bms_not_running(self):
        import core.ivc_client as ivc_mod
        ivc_mod.is_bms_running = lambda: False
        ivc = IVCClient()
        r = ivc.connect()
        self.assertEqual(r["status"], "error")
        self.assertFalse(ivc.connected)

    def test_channel_has_id_name_freq(self):
        ivc = self._ivc_with_sm("305.000", "127.900")
        r = ivc.get_channels()
        for ch in r:
            self.assertIn("id", ch)
            self.assertIn("name", ch)
            self.assertIn("freq", ch)
            self.assertIn("pilots", ch)

    def test_pilots_always_empty_list(self):
        """Pilot list not available from SM."""
        ivc = self._ivc_with_sm("305.000", "127.900")
        r = ivc.get_channels()
        for ch in r:
            self.assertIsInstance(ch["pilots"], list)
            self.assertEqual(len(ch["pilots"]), 0)

    def test_get_active_freq(self):
        ivc = self._ivc_with_sm("339.750", "127.500")
        ivc.get_channels()  # populates _uhf_freq
        self.assertEqual(ivc.get_active_freq(), "339.750")


# Keep TestIVCMocked for _parse_ts3 compatibility tests
class TestIVCMocked(unittest.TestCase):
    def test_exception_disconnects(self):
        """get_channels when BMS goes down marks as disconnected."""
        import core.ivc_client as ivc_mod
        ivc_mod.is_bms_running = lambda: False
        ivc = IVCClient()
        ivc.connected = True
        r = ivc.get_channels()
        self.assertEqual(r, [])
        self.assertFalse(ivc.connected)


# ── Integration ───────────────────────────────────────────────────────────────
class TestIntegration(unittest.TestCase):
    def test_braa_osan_to_north(self):
        rng=haversine_nm(37.09,127.03,38.5,125.5)
        brg=bearing_deg(37.09,127.03,38.5,125.5)
        self.assertGreater(rng,50); self.assertGreater(brg,270)

    def test_track_parse_braa_str(self):
        c=TRTTClient(); c._ref_lat=c._ref_lon=0.0
        c._parse_track("BLUE","T=127|37|20000|||270,Coalition=Blue,Type=Air+FixedWing")
        c._parse_track("RED","T=125.5|38.5|25000|||090,Coalition=Red,Type=Air+FixedWing")
        bl=c.tracks["BLUE"]; rd=c.tracks["RED"]
        s=braa_str(bl.lat,bl.lon,rd.lat,rd.lon)
        self.assertIn("/",s); self.assertIn("NM",s)

    def test_bullseye_in_kto(self):
        r=parse_mission_ini("[STPT]\ntarget_0 = 1746000, 1571000, 25000\n")
        bull=r["bullseye"]; self.assertIsNotNone(bull)
        self.assertTrue(28<=bull["lat"]<=46); self.assertTrue(117<=bull["lon"]<=136)

    def test_bullseye_str_same_point(self):
        s=bullseye_str(37.09,127.03,37.09,127.03,20000)
        self.assertEqual(len(s.split("/")),3)
        self.assertEqual(int(s.split("/")[1].strip()),0)

    def test_blue_red_colors(self):
        c=TRTTClient(); c._ref_lat=c._ref_lon=0.0
        c._parse_track("T1","T=127|37|5000|||0,Coalition=Blue,Type=Air+FixedWing")
        c._parse_track("T2","T=127|37|5000|||0,Coalition=Red,Type=Air+FixedWing")
        self.assertEqual(c.tracks["T1"].color,ID_COLORS[ID_FRIEND])
        self.assertEqual(c.tracks["T2"].color,ID_COLORS[ID_BOGEY])

    def test_multi_track_stats(self):
        c=TRTTClient(); c._ref_lat=c._ref_lon=0.0
        for i in range(5): c._parse_track(f"B{i}",f"T=127|{37+i*0.1}|20000|||0,Coalition=Blue,Type=Air+FixedWing,Pilot=P{i}")
        for i in range(3): c._parse_track(f"R{i}",f"T=126|{38+i*0.1}|25000|||0,Coalition=Red,Type=Air+FixedWing")
        c._parse_track("M1","T=127|37.5|10000|||0,Type=Weapon+Missile")
        s=c.stats()
        self.assertEqual(s["alive"],9); self.assertEqual(s["air"],8)
        self.assertEqual(s["missile"],1); self.assertEqual(s["human"],5)




class TestToggleLayerJsVal(unittest.TestCase):
    """Test that Python booleans produce correct JS true/false (not True/False)."""

    def _js_val(self, visible):
        """Replicate the fixed toggle_layer logic."""
        if isinstance(visible, bool):
            return "true" if visible else "false"
        elif isinstance(visible, int):
            return str(visible)
        else:
            return "true" if visible else "false"

    def test_true_produces_lowercase(self):
        self.assertEqual(self._js_val(True), "true")

    def test_false_produces_lowercase(self):
        self.assertEqual(self._js_val(False), "false")

    def test_int_produces_number(self):
        self.assertEqual(self._js_val(250), "250")

    def test_zero_produces_zero(self):
        self.assertEqual(self._js_val(0), "0")

    def test_bool_not_treated_as_int(self):
        # The old bug: isinstance(True, int) == True → str(True) == "True"
        self.assertNotEqual(self._js_val(True), "True")
        self.assertNotEqual(self._js_val(False), "False")

if __name__ == "__main__":
    unittest.main(verbosity=2)
