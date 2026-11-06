import os
import time
from datetime import datetime, timedelta
import pytz
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import swisseph as swe
import streamlit as st
from google import genai
from google.genai import types

# ==============================================================
# 🔴 API KEY பாதுகாப்பு (Streamlit Secrets அல்லது Environment Variable)
# ==============================================================
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))

st.set_page_config(page_title="ஜோதிட வாழ்க்கை வரைபடம் 2026", page_icon="🔮", layout="centered")

# ==========================================
# 🌌 ஜோதிட மாறிலிகள் & சூத்திரங்கள்
# ==========================================
NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"
]
PLANET_LORDS = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
PLANET_YEARS = [("Ketu", 7), ("Venus", 20), ("Sun", 6), ("Moon", 10), ("Mars", 7), 
                ("Rahu", 18), ("Jupiter", 16), ("Saturn", 19), ("Mercury", 17)]
ZODIAC_SIGNS = ["Mesha", "Rishaba", "Mithuna", "Kataka", "Simha", "Kanya", "Thula", "Vrischika", "Dhanus", "Makara", "Kumbha", "Meena"]
PLANETS_MAP = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER, "Venus": swe.VENUS, "Saturn": swe.SATURN, "Rahu": swe.MEAN_NODE
}

def get_star_and_sublord(longitude):
    nak_span = 360.0 / 27.0
    nak_idx = int(longitude / nak_span)
    star_name = NAKSHATRAS[nak_idx % 27]
    star_lord = PLANET_LORDS[nak_idx % 9]
    pada = int((longitude % nak_span) / (nak_span / 4.0)) + 1
    rem_deg = longitude - (nak_idx * nak_span)
    start_lord_idx = PLANET_LORDS.index(star_lord)
    accum_span = 0.0
    sub_lord = star_lord
    for i in range(9):
        curr_p, yrs = PLANET_YEARS[(start_lord_idx + i) % 9]
        span = (yrs / 120.0) * nak_span
        if rem_deg <= (accum_span + span):
            sub_lord = curr_p
            break
        accum_span += span
    return star_name, pada, star_lord, sub_lord

def get_navamsa_sign(lon):
    element_starts = [0, 9, 6, 3]
    return ZODIAC_SIGNS[(element_starts[int(lon / 30) % 4] + int((lon % 30) / (30.0 / 9.0))) % 12]

def get_dasamsa_sign(lon):
    s_idx = int(lon / 30)
    part = int((lon % 30) / 3.0)
    return ZODIAC_SIGNS[(s_idx + part) % 12] if s_idx % 2 == 0 else ZODIAC_SIGNS[(s_idx + 8 + part) % 12]

def get_saptamsa_sign(lon):
    s_idx = int(lon / 30)
    part = int((lon % 30) / (30.0 / 7.0))
    return ZODIAC_SIGNS[(s_idx + part) % 12] if s_idx % 2 == 0 else ZODIAC_SIGNS[(s_idx + 6 + part) % 12]

# ==========================================
# 📱 மொபைல் இடைமுகம்
# ==========================================
st.title("🔮 ஸ்ரீ ஜோதிட ஆச்சாரியார்")
st.caption("2026 எதார்த்த வாழ்க்கை வரைபடம் (11-Block ஆழமான ஆய்வு & சுவிஸ் எபிமெரிஸ் கணிதம்)")

# கிளவுடில் API Key இல்லையென்றால் பயனரே உள்ளிடும் வசதி
if not GEMINI_API_KEY:
    GEMINI_API_KEY = st.text_input("🔑 உங்கள் Gemini API Key உள்ளிடவும்:", type="password")

with st.form("astro_form"):
    st.subheader("📋 ஜாதகர் விவரங்கள்")
    name = st.text_input("1. ஜாதகர் பெயர்:", value="மாலதி")
    col1, col2 = st.columns(2)
    with col1:
        dob_str = st.text_input("2. பிறந்த தேதி (YYYY-MM-DD):", value="1995-05-15")
    with col2:
        tob_str = st.text_input("3. பிறந்த நேரம் 24-hr (HH:MM):", value="14:30")
    place_name = st.text_input("4. பிறந்த ஊர், மாநிலம்:", value="Madurai, Tamil Nadu")
    
    col3, col4 = st.columns(2)
    with col3:
        gender = st.selectbox("5. பாலினம்:", ["பெண் (Female)", "ஆண் (Male)"])
    with col4:
        life_role = st.selectbox("6. தற்போதைய நிலை:", ["இல்லத்தரசி (Homemaker)", "தனியார் வேலை (Private Job)", "அரசு வேலை (Govt Job)", "சுயதொழில் / வியாபாரம் (Business)", "படிப்பு / மாணவர் (Student)", "வேலையின்மை"])
    
    marital_status = st.selectbox("7. திருமண நிலை:", ["திருமணம் ஆனவர்", "திருமணம் ஆகாதவர்", "விவாகரத்து ஆனவர்", "2-ம் திருமணம் தேடுபவர்", "பிரிந்து வாழ்பவர்"])
    
    submit_btn = st.form_submit_button("🚀 11-Block முழு ஜாதகம் கணிக்கவும்", use_container_width=True)

# ==========================================
# ⚙️ கணிதம்
# ==========================================
if submit_btn:
    if not GEMINI_API_KEY:
        st.error("⚠️ தயவுசெய்து Gemini API சாவியை உள்ளிடவும்!")
        st.stop()

    with st.spinner("⏳ சுவிஸ் எபிமெரிஸ் மூலம் கிரக பாகைகள், KP சப்-லார்ட்கள், வாழ்நாள் தசா-புக்தி மற்றும் லைவ் கோட்சாரம் கணக்கிடப்படுகிறது..."):
        try:
            geolocator = Nominatim(user_agent="jathaga_app_live_v2", timeout=10)
            loc = geolocator.geocode(place_name)
            if not loc:
                st.error("⚠️ பிறந்த ஊர் பெயர் கூகுள் மேப்பில் கிடைக்கவில்லை. சரியான ஊர் மற்றும் மாநிலத்தை உள்ளிடவும் (எ.கா: Madurai, Tamil Nadu).")
                st.stop()

            tf = TimezoneFinder()
            tz_str = tf.timezone_at(lng=loc.longitude, lat=loc.latitude)
            if not tz_str:
                st.error("⚠️ கால மண்டலத்தை (Timezone) கண்டறிய முடியவில்லை.")
                st.stop()

            tz = pytz.timezone(tz_str)
            birth_dt = datetime.strptime(f"{dob_str.strip()} {tob_str.strip()}", "%Y-%m-%d %H:%M")
            local_dt = tz.localize(birth_dt)
            utc_dt = local_dt.astimezone(pytz.utc)

            hour_decimal = utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0
            jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, hour_decimal)
            swe.set_sid_mode(swe.SIDM_KRISHNAMURTI)

            cusps, ascmc = swe.houses_ex(jd, loc.latitude, loc.longitude, b'P', swe.FLG_SIDEREAL)
            lagna_lon = ascmc[0] % 360
            l_sign_idx = int(lagna_lon / 30)
            l_star, l_pada, l_star_l, l_sub_l = get_star_and_sublord(lagna_lon)

            planets_data = [{
                "name": "Lagna (Asc)", "lon": lagna_lon, "sign": ZODIAC_SIGNS[l_sign_idx],
                "deg": f"{int(lagna_lon%30):02d}° {int(((lagna_lon%30)%1)*60):02d}'",
                "star": l_star, "pada": l_pada, "star_lord": l_star_l, "sub_lord": l_sub_l, "retro": "-",
                "d9": get_navamsa_sign(lagna_lon), "d10": get_dasamsa_sign(lagna_lon), "d7": get_saptamsa_sign(lagna_lon)
            }]

            moon_lon = 0
            for p_name, p_code in PLANETS_MAP.items():
                res, _ = swe.calc_ut(jd, p_code, swe.FLG_SIDEREAL | swe.FLG_SWIEPH)
                lon = res[0] % 360
                speed = res[3]
                is_retro = "வக்ரம் (R)" if speed < 0 else "நேர்கதி (D)"
                s_idx = int(lon / 30)
                star, pada, star_l, sub_l = get_star_and_sublord(lon)
                planets_data.append({
                    "name": p_name, "lon": lon, "sign": ZODIAC_SIGNS[s_idx],
                    "deg": f"{int(lon%30):02d}° {int(((lon%30)%1)*60):02d}'",
                    "star": star, "pada": pada, "star_lord": star_l, "sub_lord": sub_l, "retro": is_retro,
                    "d9": get_navamsa_sign(lon), "d10": get_dasamsa_sign(lon), "d7": get_saptamsa_sign(lon)
                })
                if p_name == "Moon": 
                    moon_lon = lon

            rahu_obj = next(p for p in planets_data if p['name'] == 'Rahu')
            ketu_lon = (rahu_obj['lon'] + 180) % 360
            k_idx = int(ketu_lon / 30)
            k_star, k_pada, k_star_l, k_sub_l = get_star_and_sublord(ketu_lon)
            planets_data.append({
                "name": "Ketu", "lon": ketu_lon, "sign": ZODIAC_SIGNS[k_idx],
                "deg": f"{int(ketu_lon%30):02d}° {int(((ketu_lon%30)%1)*60):02d}'",
                "star": k_star, "pada": k_pada, "star_lord": k_star_l, "sub_lord": k_sub_l, "retro": "வக்ரம் (R)",
                "d9": get_navamsa_sign(ketu_lon), "d10": get_dasamsa_sign(ketu_lon), "d7": get_saptamsa_sign(ketu_lon)
            })

            cusps_data = []
            for i in range(12):
                c_lon = cusps[i] % 360
                s_idx = int(c_lon / 30)
                star, pada, star_l, sub_l = get_star_and_sublord(c_lon)
                cusps_data.append({
                    "house": i + 1, "sign": ZODIAC_SIGNS[s_idx],
                    "deg": f"{int(c_lon%30):02d}° {int(((c_lon%30)%1)*60):02d}'",
                    "star": star, "pada": pada, "star_lord": star_l, "sub_lord": sub_l
                })

            nak_span = 360.0 / 27.0
            nak_idx = int(moon_lon / nak_span)
            m_star_lord = PLANET_LORDS[nak_idx % 9]
            rem_in_nak = (nak_idx + 1) * nak_span - moon_lon
            balance_years = (rem_in_nak / nak_span) * dict(PLANET_YEARS)[m_star_lord]

            dasha_periods = []
            curr_start = birth_dt - timedelta(days=(dict(PLANET_YEARS)[m_star_lord] - balance_years) * 365.25)
            start_idx = PLANET_LORDS.index(m_star_lord)
            for i in range(9):
                p_name, yrs = PLANET_YEARS[(start_idx + i) % 9]
                curr_end = curr_start + timedelta(days=yrs * 365.25)
                dasha_periods.append({"planet": p_name, "years": yrs, "start": curr_start, "end": curr_end})
                curr_start = curr_end

            today = datetime.now()
            lifetime_bhuktis_text = f"\n[வாழ்நாள் விம்சோத்தரி தசா-புக்தி அட்டவணை (பிறப்பு முதல் 80+ வயது வரை)]:\n👉 பிறப்பில் தசா இருப்பு: {m_star_lord} தசா {int(balance_years)} வருடங்கள், {int((balance_years%1)*12)} மாதங்கள்\n"
            for d_idx in range(min(6, len(dasha_periods))):
                md = dasha_periods[d_idx]
                md_st_str = birth_dt.strftime('%d-%b-%Y') if md['start'] < birth_dt else md['start'].strftime('%d-%b-%Y')
                lifetime_bhuktis_text += f"\n--- {md['planet']} மகா தசா ({md_st_str} முதல் {md['end'].strftime('%d-%b-%Y')} வரை) ---\n"
                p_idx = PLANET_LORDS.index(md['planet'])
                b_curr_start = md['start']
                for j in range(9):
                    b_planet, b_years = PLANET_YEARS[(p_idx + j) % 9]
                    b_curr_end = b_curr_start + timedelta(days=(md['years'] * b_years / 120.0) * 365.25)
                    if b_curr_end >= birth_dt:
                        status = "👉 [தற்போது நடப்பது / RUNNING NOW]" if b_curr_start <= today <= b_curr_end else ""
                        b_st = birth_dt.strftime('%d-%b-%Y') if b_curr_start < birth_dt else b_curr_start.strftime('%d-%b-%Y')
                        lifetime_bhuktis_text += f"  • {md['planet']} - {b_planet:<10}: {b_st} முதல் {b_curr_end.strftime('%d-%b-%Y')} வரை {status}\n"
                    b_curr_start = b_curr_end

            now_utc = datetime.now(pytz.utc)
            jd_now = swe.julday(now_utc.year, now_utc.month, now_utc.day, now_utc.hour + now_utc.minute / 60.0)
            transit_text = f"\n[இன்றைய லைவ் கோட்சார கிரக நிலைகள் - {today.strftime('%d-%b-%Y')}]:\n"
            for tp_name in ["Saturn", "Jupiter", "Mars", "Rahu"]:
                res, _ = swe.calc_ut(jd_now, PLANETS_MAP[tp_name], swe.FLG_SIDEREAL | swe.FLG_SWIEPH)
                t_lon = res[0] % 360
                t_s_idx = int(t_lon / 30)
                _, _, _, t_sub_l = get_star_and_sublord(t_lon)
                transit_text += f"- கோட்சார {tp_name}: {ZODIAC_SIGNS[t_s_idx]} ({int(t_lon%30):02d}° {int(((t_lon%30)%1)*60):02d}') | Sub: {t_sub_l} | ராசிக்கு {((t_s_idx - ZODIAC_SIGNS.index(planets_data[1]['sign'])) % 12) + 1}-ம் இடம்\n"

            chart_data = f"""
பெயர்: {name} | பாலினம்: {gender} | தற்போதைய நிலை: {life_role} | திருமண நிலை: {marital_status}
பிறந்த தேதி: {dob_str} | நேரம்: {tob_str} | இடம்: {place_name}
லக்னம்: {ZODIAC_SIGNS[l_sign_idx]} ({int(lagna_lon%30):02d}° {int(((lagna_lon%30)%1)*60):02d}') | நட்சத்திரம்: {l_star}-{l_pada}
ராசி: {planets_data[1]['sign']} | நட்சத்திரம்: {planets_data[1]['star']}-{planets_data[1]['pada']}

[கிரக நிலைகள் & KP SUB-LORDS]:
"""
            for p in planets_data: chart_data += f"- {p['name']}: {p['sign']} {p['deg']} | Star: {p['star']}-{p['pada']} ({p['star_lord']}) | Sub: {p['sub_lord']} | {p['retro']}\n"
            chart_data += "\n[KP பாவ ஆரம்பங்கள் (CUSPS 1-12) & SUB-LORDS]:\n"
            for c in cusps_data: chart_data += f"- பாவம் {c['house']}: {c['sign']} {c['deg']} | Star: {c['star']}-{c['pada']} ({c['star_lord']}) | Sub: {c['sub_lord']}\n"
            chart_data += "\n[வர்க்கக் கட்டங்கள் (D1, D9, D10, D7)]:\n"
            for p in planets_data: chart_data += f"- {p['name']}: D1 {p['sign']} | D9 {p['d9']} | D10 {p['d10']} | D7 {p['d7']}\n"
            chart_data += lifetime_bhuktis_text + transit_text

            st.session_state["chart_data"] = chart_data
            st.session_state["name"] = name
            if "prediction_book" in st.session_state:
                del st.session_state["prediction_book"]
            st.success("✅ சுவிஸ் எபிமெரிஸ் கணிதம் & வாழ்நாள் தசா-புக்தி முடிந்தது!")

        except Exception as e:
            st.error(f"⚠️ கணிதத்தில் பிழை: {e}")

# ==============================================================
# 🧠 AI வாழ்க்கை வரலாறு உருவாக்குதல் (முழுமையான 11 BLOCKS)
# ==============================================================
if "chart_data" in st.session_state and "prediction_book" not in st.session_state:
    st.info("🚀 இப்போது 11-Block முழுமையான ஆழமான வாழ்க்கை வரலாற்று நூல் தயாராகிறது (சுமார் 1–2 நிமிடங்கள் ஆகும்)...")
    progress_bar = st.progress(0)
    
    # 🔴 உங்கள் முழுமையான விதிகள் அனைத்தும் அச்சு மாறாமல் இங்கே உள்ளது!
    SYSTEM_RULES = """
🔥 THE 2026 REALITY SUPREME MASTER ENGINE

🧠 ROLE DEFINITION & ARCHIVAL PERSONA:
நீங்கள் 40+ வருட ஆழ்ந்த அனுபவம் கொண்ட முதன்மை ஜோதிட ஆச்சாரியார் (Senior Jyotish Acharya).
பிருஹத் பராசரர், பலதீபிகை, சாராவளி, புலிப்பாணி சித்தர் மற்றும் KP 249 சப்-லார்ட் விதிகளின் அத்தனை ஞானமும் உங்கள் உள்மன ஆய்வில் (Silent Background Engine) முழுமையாக இயங்க வேண்டும். ஆனால் வெளியே பேசும்போது ஜோதிடப் புத்தக விவாதங்கள் இல்லாமல், அசல் வாழ்க்கைப் பலன்கள் மட்டுமே வர வேண்டும்.
Voice & Tone: ஒரு முதிர்ந்த ஞானியின் கனிவான, அதே சமயம் சமரசமற்ற, முகத்தில் அடித்தாற்போல் உண்மைகளைப் பேசும் காரசாரமான நடை (Honest, Direct & Strictly No Sugarcoating).

🔴 MANDATORY LANGUAGE & WRITING RULES:
1. எளிய, நவீன தமிழ் நடை: புரியாத பழைய தூய தமிழ் வார்த்தைகளைத் தவிர்க்கவும் (எ.கா: "கூட்டாண்மை" என எழுதாமல் "பார்ட்னர்ஷிப் (Partnership)" என எழுதவும்; "களத்திரம்" என எழுதாமல் "வாழ்க்கைத் துணை (Spouse)" என எழுதவும்). தமிழ் மற்றும் ஆங்கிலக் கலைச்சொற்கள் அடைப்புக்குறிக்குள் தெளிவாக வரலாம் (எ.கா: IVF சிகிச்சை, Love Breakup, Career, Sub-lord). எழுத்துப் பிழைகளோ, குறியீட்டுக் குழப்பங்களோ இருக்கக்கூடாது.
2. இரு அடுக்கு வெளியீட்டு நடை (Dual-Layer Structure):
   - அ) விரிவான வாழ்வியல் கதை (Detailed Narrative Reading).
   - ஆ) ஜோதிட சான்றுப் பெட்டி (காரணமான கிரகம், பாவ சப்-லார்ட், தசா குறித்த நேரடி விளக்கம்).
   - இ) ஒவ்வொரு பிளாக்கிலும் குறைந்தது 3 முதல் 5 நிஜ வாழ்க்கைச் சம்பவங்கள் (Real-Life Scenarios).
3. கால நிர்ணயப் பொன்விதி: "Dasha = அனுமதி (Sanction), Transit (கோட்சாரம்) = தூண்டுதல் (Trigger)."

🔴 MANDATORY ASTROLOGICAL GUARDRAILS & LOGIC ENGINE (கட்டாய ஜோதிடத் தணிக்கை விதிகள்):
1. RULE OF DIGNITY OVERRIDE (ஆட்சி / உச்ச பல விதி):
   - ஒரு கிரகம் 6, 8, 12 ஆகிய மறைவிடங்களில் நின்றாலும், அது தனது சொந்த வீட்டிலோ (Swakshetra) அல்லது உச்ச வீட்டிலோ (Exalted) நின்றால், அது அந்த பாவத்தைக் கெடுக்காது; மாறாகத் தன் சொந்த காரகத்துவத்தைப் பாதுகாக்கும். எக்காரணம் கொண்டும் ஆட்சி/உச்சம் பெற்ற கிரகத்திற்கு "முழுமையான அழிவு, இழப்பு, புத்திரக் கேடு, வறுமை" போன்ற குருட்டுப் பலன்களை எழுதக் கூடாது.
2. SHADOW PLANET AGENT PROTOCOL (ராகு/கேது பிரதிநிதித்துவ விதி):
   - ராகு அல்லது கேதுவை வெறும் அசுப கிரகமாகவோ நேரடியாக எடுக்கக் கூடாது. ராகு/கேது அமர்ந்த ராசிநாதன் யார்? அந்த ராசிநாதன் எந்த பாவத்திற்கு அதிபதி? என்பதைப் பார்க்க வேண்டும். அந்த ராசிநாதன் சுப பலன் தரும் பாவத்திற்கு அதிபதியாக இருந்தால், ராகு/கேது அந்த ராசிநாதனின் சுப பலனையே (Agent of the Dispositor) தரும்.
3. KP SIGNIFICATION BALANCE (2, 5, 11 vs 6, 8, 12 சமநிலை விதி):
   - ஒரு சப்-லார்ட் 8 அல்லது 12-ஐ தொடர்பு கொண்டாலும், அதே சமயம் 2, 5, 11-ஐயும் தொடர்பு கொண்டால் நிகழ்வு உறுதியாக நடக்கும். 8 மற்றும் 12 என்பது அதற்காகச் செய்யும் செலவு, மன அழுத்தம் அல்லது பிரசவ முறை (C-Section/Surgery) போன்ற 'வழியை' மட்டுமே குறிக்கும்.
4. SEPARATION OF "EVENT DENIAL" VS "DELIVERY MODE" (நிகழ்வு மறுப்பு vs நிகழும் விதம்):
   - தாமதத்திற்கும் (Delay), மறுப்பிற்கும் (Denial), மருத்துவ உதவிக்கும் உள்ள வித்தியாசத்தை உணர வேண்டும். செவ்வாய், சனி சம்பந்தப்பட்டால் அது அறுவை சிகிச்சை (Surgery / C-Section)-ஐக் குறிக்குமே தவிர, தானாகவே IVF அல்லது மலட்டுத்தன்மை ஆகாது. தீவிர கிரகப் பாதிப்புகள் இருந்தால் மட்டுமே தீவிர மருத்துவ மலட்டுத்தன்மையை (Infertility/IVF) கணிக்க வேண்டும்.
5. PRE-FLIGHT REALITY AUDIT:
   - பலனைத் திரையில் எழுதுவதற்கு முன், இது வெறும் 8-ம் பாவ பயமுறுத்தலா அல்லது லக்ன/ராசி பலம், ஆட்சி பலம் மற்றும் 2, 11 பாவங்களின் பலத்தை ஒப்பிட்டுப் பார்த்து எழுதப்படும் சமநிலையான எதார்த்தமா என சுயதணிக்கை செய்ய வேண்டும்.
"""

    BLOCKS_CONFIG = [
        {
            "num": 1,
            "title": "BLOCK 1: அகம், ஆளுமை மற்றும் நிஜ முகம் (CORE PERSONALITY & HIDDEN MINDSET)",
            "task": """
கீழ்க்கண்ட BLOCK 1-ஐ தணிக்கை விதிகளுடன் முழு ஆழத்துடன் விரிவாக எழுதுக:
🔹 BLOCK 1: அகம், ஆளுமை மற்றும் நிஜ முகம் (CORE PERSONALITY & HIDDEN MINDSET)
- லக்னம், லக்னாதிபதி மற்றும் 1-ம் பாவ Sub-lord ஆய்வு.
- வெளி உலகிற்கு காட்டும் நல்லவர் முகம் vs உள்ளுக்குள் இருக்கும் உண்மையான குணம் மற்றும் பிடிவாதம்.
- இவரின் மிகப்பெரிய பலம் என்ன? யாராலும் மாற்ற முடியாத பலவீனம் அல்லது முன்கோபம் என்ன?
- 3 முதல் 5 நிஜ வாழ்க்கை அன்றாடச் சம்பவங்கள் (Real-Life Scenarios).
"""
        },
        {
            "num": 2,
            "title": "BLOCK 2: கர்ம வித்து மற்றும் நவாம்ச பலம் (NAVAMSA & HIDDEN KARMA)",
            "task": """
கீழ்க்கண்ட BLOCK 2-ஐ முழு ஆழத்துடன் விரிவாக எழுதுக:
🔹 BLOCK 2: கர்ம வித்து மற்றும் நவாம்ச பலம் (NAVAMSA & HIDDEN KARMA)
- ராசி (D1) மற்றும் நவாம்சம் (D9) ஒப்பீடு: 28-32 வயதுக்கு பிறகு அல்லது திருமணத்திற்குப் பிறகு வாழ்வில் ஏற்படும் உள்மன மற்றும் உலகியல் மாற்றங்கள்.
- வர்கோத்தமம் அல்லது நீசபங்கம் பெற்றுள்ள கிரகங்கள் தரும் கர்ம பலம்.
- ராகு - கேது அச்சு மற்றும் ஆத்மகாரகன் (Atmakaraka) காட்டும் ஆன்ம நோக்கம் & கர்மக் கடன்.
- 3 முதல் 5 நிஜ வாழ்க்கைச் சம்பவங்கள்.
"""
        },
        {
            "num": 3,
            "title": "BLOCK 3: இளமைப் பருவம், காதல் மற்றும் உணர்வுக் காயங்கள் (YOUTH, LOVE & HEARTBREAKS)",
            "task": """
கீழ்க்கண்ட BLOCK 3-ஐ எந்தவொரு சுகர்கோட்டிங்கும் இன்றி உண்மையாக எழுதுக:
🔹 BLOCK 3: இளமைப் பருவம், காதல் மற்றும் உணர்வுக் காயங்கள் (YOUTH, LOVE & HEARTBREAKS)
- 16 முதல் 25 வயது வரையிலான காலகட்டத்தில் 5-ம் பாவம், சுக்கிரன், செவ்வாய், ராகு/கேது ஆய்வு.
- இளமையில் ஏற்பட்ட காதல் ஈர்ப்பு, அதனால் வந்த குடும்ப அவமானங்கள் அல்லது ரகசிய உறவுகள்.
- துரோகம், நம்பிக்கை துரோகம் (Betrayal), பிரேக்-அப் (Breakup) அல்லது காதல் தோல்வி ஏற்பட்டதா? அந்த மனக்காயம் இவரை எப்படி மாற்றியது?
- 3 முதல் 5 நிஜ வாழ்க்கைச் சம்பவங்கள்.
"""
        },
        {
            "num": 4,
            "title": "BLOCK 4: திருமணம், தாம்பத்தியம் மற்றும் குடும்ப எதார்த்தம் (MARRIAGE & IN-LAW DYNAMICS)",
            "task": """
கீழ்க்கண்ட BLOCK 4-ஐ ஜாதகர் குறிப்பிட்ட திருமண நிலைக்கு ஏற்ப மிக ஆழமாக எழுதுக:
🔹 BLOCK 4: திருமணம், தாம்பத்தியம் மற்றும் குடும்ப எதார்த்தம் (MARRIAGE & IN-LAW DYNAMICS)
- திருமண நிலைக்கேற்ப ஆய்வு (திருமணம் ஆனவர் / ஆகாதவர் / விவாகரத்து / 2-ம் திருமணம் தேடுபவர் / பிரிந்து வாழ்பவர்).
- 7-ம் பாவ Sub-lord மற்றும் சுக்கிரன்/குரு நிலை:
  * திருமணம் சுமூகமாக அமைந்ததா? அல்லது கடுமையான தடைகள், இழுபறிகள், எதிர்ப்புகளுக்குப் பின் அமைந்ததா?
  * வாழ்க்கை துணையின் உண்மையான சுபாவம், ஈகோ மற்றும் தாம்பத்திய ஒற்றுமை.
  * விவாகரத்து, பிரிவு அல்லது 2-ம் திருமண யோகம் (9 & 11-ம் பாவங்கள்) உள்ளதா? (No Sugarcoating).
  * புகுந்த வீட்டில் மாமியார், நாத்தனார் போன்ற உறவுகளால் ஏற்படும் மறைமுகப் பனிப்போர் மற்றும் மன உளைச்சல்கள் (10-ம் மற்றும் 3-ம் பாவ தொடர்புகள்).
- 3 முதல் 5 நிஜ வாழ்க்கைச் சம்பவங்கள்.
"""
        },
        {
            "num": 5,
            "title": "BLOCK 5: புத்திர பாக்கியம் மற்றும் மருத்துவ எதார்த்தம் (PROGENY & IVF / MEDICAL CONCEPTION)",
            "task": """
கீழ்க்கண்ட BLOCK 5-ஐ "SEPARATION OF EVENT DENIAL VS DELIVERY MODE" விதியைப் பின்பற்றி எழுதுக:
🔹 BLOCK 5: புத்திர பாக்கியம் மற்றும் மருத்துவ எதார்த்தம் (PROGENY & IVF / MEDICAL CONCEPTION)
- 5-ம் பாவ Sub-lord, குரு மற்றும் D7 சப்தாம்ச ஆய்வு.
- குழந்தை பிறப்பு இயல்பாக (Natural Conception) நடக்குமா?
- அல்லது கடுமையான தாமதம் ஏற்பட்டு IUI, IVF (செயற்கைக் கருத்தரித்தல்), லேப்ராஸ்கோபி போன்ற தீவிர மருத்துவ சிகிச்சைகள் மூலமாக மட்டுமே குழந்தை சாத்தியமா? (அறுவை சிகிச்சை சி-செக்ஷனுக்கும், மலட்டுத்தன்மைக்கும் உள்ள வித்தியாசத்தை உணர்ந்து எழுதுக).
- பிறக்கும் குழந்தைகளின் எதிர்கால வளர்ச்சி, குணம் மற்றும் பெற்றோரிடம் காட்டும் பாசம்/முரண்பாடு.
- 3 முதல் 5 நிஜ வாழ்க்கைச் சம்பவங்கள்.
"""
        },
        {
            "num": 6,
            "title": "BLOCK 6: வாழ்வாதாரம், உத்தியோகம் அல்லது குடும்ப நிர்வாகம் (CAREER / HOMEMAKER DYNAMICS)",
            "task": """
கீழ்க்கண்ட BLOCK 6-ஐ ஜாதகர் குறிப்பிட்ட நிலைக்கு ஏற்ப (இல்லத்தரசி vs உத்தியோகம்) விரிவாக எழுதுக:
🔹 BLOCK 6: வாழ்வாதாரம், உத்தியோகம் அல்லது குடும்ப நிர்வாகம் (CAREER / HOMEMAKER DYNAMICS)
- உத்தியோகம்/தொழில் செய்பவர் என்றால்: 10-ம் பாவ Sub-lord, D10 அடிப்படையில் வேலை மாற்றம், ஆபிஸ் பாலிடிக்ஸ், தொழில் உச்சம்.
- இல்லத்தரசி (Homemaker) என்றால்: வீட்டின் வரவு-செலவு அதிகாரம், புகுந்த வீட்டில் இவருக்கு இருக்கும் கௌரவம், சுயமாகச் சம்பாதிக்க வேண்டும் என்ற உள்மன ஏக்கம் மற்றும் அதற்கான வாய்ப்புகள்.
- 3 முதல் 5 நிஜ வாழ்க்கைச் சம்பவங்கள்.
"""
        },
        {
            "num": 7,
            "title": "BLOCK 7: பொருளாதாரம், சொத்து மற்றும் கடன் அபாயங்கள் (WEALTH, PROPERTY & DEBT TRAPS)",
            "task": """
கீழ்க்கண்ட BLOCK 7-ஐ விரிவாக எழுதுக:
🔹 BLOCK 7: பொருளாதாரம், சொத்து மற்றும் கடன் அபாயங்கள் (WEALTH, PROPERTY & DEBT TRAPS)
- 2 மற்றும் 11-ம் பாவ Sub-lord (பண வரவு மற்றும் சேமிப்பு).
- சொந்த வீடு, நிலம், பூர்வீக சொத்து சேர்க்கை மற்றும் வாகன யோகம் எப்போது கூடிவரும்?
- பண விரயங்கள், ஏமாற்றங்கள் மற்றும் கடன் வலையில் (Debt Traps) விழக்கூடிய அபாய காலங்கள்.
- 3 முதல் 5 நிஜ வாழ்க்கைச் சம்பவங்கள்.
"""
        },
        {
            "num": 8,
            "title": "BLOCK 8: ஆயுள், ஆரோக்கியம் மற்றும் கண்ட காலங்கள் (LONGEVITY, HEALTH & CRISIS PERIODS)",
            "task": """
கீழ்க்கண்ட BLOCK 8-ஐ ஆயுள் மற்றும் மாரக/பாதக விதிகளுடன் விரிவாக எழுதுக:
🔹 BLOCK 8: ஆயுள், ஆரோக்கியம் மற்றும் கண்ட காலங்கள் (LONGEVITY, HEALTH & CRISIS PERIODS)
- லக்ன Sub-lord மற்றும் 8-ம் பாவ Sub-lord காட்டும் ஆயுள் பலம் (அற்பாயுள்: 0-33 / மத்தியாயுள்: 34-66 / தீர்க்காயுள்: 67-85+).
- உடல் உறுப்பு பாதிப்புகள் (இதயம், ரத்தம், நரம்பு, எலும்பு, கர்ப்பப்பை, சர்க்கரை போன்ற பலவீனங்கள்).
- 2, 7-ம் மாரகம் மற்றும் பாதக ஸ்தானங்கள் தூண்டப்படும் விபத்து, கண்ட காலங்கள் மற்றும் தீவிர மருத்துவ சிகிச்சை தேவைப்படும் வயது வரம்புகள்.
- 3 முதல் 5 நிஜ வாழ்க்கைச் சம்பவங்கள்.
"""
        },
        {
            "num": 9,
            "title": "BLOCK 9: காலச்சக்கரம் - வாழ்நாள் தசா புத்தி காலவரிசை (DASHA BIOGRAPHY)",
            "task": """
கீழ்க்கண்ட BLOCK 9-ஐ வாழ்நாள் தசா-புக்தி அட்டவணையின் அடிப்படையில் விரிவாக எழுதுக:
🔹 BLOCK 9: காலச்சக்கரம் - தசா புத்தி காலவரிசை (DASHA BIOGRAPHY)
- கடந்து வந்த தசாக்களின் முக்கிய திருப்புமுனைகள்.
- தற்போதைய மகா தசா மற்றும் நடப்பு புக்தியின் (RUNNING NOW) உண்மை முகம்: தற்போது காலம் இவரிடம் என்ன எதிர்பார்க்கிறது?
- அடுத்த 3 முதல் 5 ஆண்டுகளுக்கான முக்கிய நிகழ்வு வாய்ப்புகள் மற்றும் கடுமையான எச்சரிக்கைகள்.
- 3 முதல் 5 நிஜ வாழ்க்கைச் சம்பவங்கள்.
"""
        },
        {
            "num": 10,
            "title": "BLOCK 10: நடப்பு கோட்சார காலக்கண்ணாடி (REAL-TIME TRANSIT IMPACT - NEXT 1-3 YEARS)",
            "task": """
கீழ்க்கண்ட BLOCK 10-ஐ இன்றைய லைவ் கோட்சார கிரக நிலைகளை அடிப்படையாக வைத்து எழுதுக:
🔹 BLOCK 10: நடப்பு கோட்சார காலக்கண்ணாடி (REAL-TIME TRANSIT IMPACT - NEXT 1-3 YEARS)
- இன்றைய கோட்சார கிரகங்களின் (சனி, குரு, ராகு-கேது) சேர்க்கை நடப்பு தசா-புக்தியோடு இணையும் விதம்.
- அடுத்த 1 முதல் 3 ஆண்டுகளில் அன்றாட வாழ்வில் உருவாகும் 3 முதல் 5 நடைமுறை நிகழ்வுகள்.
"""
        },
        {
            "num": 11,
            "title": "BLOCK 11: கர்ம பரிகாரங்கள் & இறுதி வாழ்வியல் வரைபடம் (PRACTICAL REMEDIES & SOUL BLUEPRINT)",
            "task": """
கீழ்க்கண்ட BLOCK 11-ஐ முழுமையாக எழுதி நிறைவு செய்க:
🔹 BLOCK 11: கர்ம பரிகாரங்கள் & இறுதி வாழ்வியல் வரைபடம் (PRACTICAL REMEDIES & SOUL BLUEPRINT)
- எளிய குலதெய்வ / ஆன்மீக வழிகாட்டல்கள்.
- மாற்றிக்கொள்ள வேண்டிய சுபாவங்கள் (Behavioral Corrections) மற்றும் தவிர்க்க வேண்டிய தவறுகள்.
- ஜாதகர் தன் விதியை வென்று வாழ கடைப்பிடிக்க வேண்டிய ஒற்றை வாழ்வியல் தாரக மந்திரம்.
"""
        }
    ]

    client = genai.Client(api_key=GEMINI_API_KEY)
    full_book = []
    
    for b_idx, block in enumerate(BLOCKS_CONFIG):
        st.write(f"⏳ ஆய்வு செய்யப்படுகிறது ({b_idx + 1}/11): **{block['title']}**...")
        block_text = None
        
        prompt_content = f"""
ஜாதகரின் அசல் தொழில்நுட்பத் தரவுகள், வாழ்நாள் தசா-புக்தி & சூழல்:
{st.session_state['chart_data']}

பணி:
{block['task']}
"""
        # அதிகாரப்பூர்வ Gemini 2.5 Flash / 1.5 Flash மாடல்கள் மட்டுமே பயன்படுத்தப்பட்டுள்ளது
        try:
            resp = client.models.generate_content(
                model="gemini-2.5-flash", 
                contents=prompt_content,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_RULES,
                    temperature=0.4
                )
            )
            block_text = resp.text
        except Exception:
            time.sleep(2)
            try:
                resp = client.models.generate_content(
                    model="gemini-1.5-flash", 
                    contents=prompt_content,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_RULES,
                        temperature=0.4
                    )
                )
                block_text = resp.text
            except Exception as e:
                block_text = f"⚠️ தற்காலிக சர்வர் பிழை: {e}"

        full_book.append(f"\n\n---\n## 📖 {block['title']}\n\n" + block_text)
        progress_bar.progress((b_idx + 1) / 11)
        time.sleep(1)

    st.session_state["prediction_book"] = "\n".join(full_book)
    st.success("🎉 11-Block முழுமையான ஆழமான வாழ்க்கை வரலாற்று நூல் தயாராகிவிட்டது!")

# ==========================================
# 📖 திரையில் காட்டுதல் & PDF / Text பதிவிறக்கம்
# ==========================================
if "prediction_book" in st.session_state:
    st.divider()
    st.subheader(f"📖 {st.session_state['name']} அவர்களின் முழுமையான ஜாதக நூல்")
    
    full_report_text = f"ஜாதக தொழில்நுட்பத் தரவுகள் & வாழ்நாள் தசா-புக்தி:\n{st.session_state['chart_data']}\n\n" + st.session_state["prediction_book"]
    
    st.download_button(
        label="📥 முழு ஜாதக அறிக்கையை பதிவிறக்கம் செய்க (Download Full Report)",
        data=full_report_text,
        file_name=f"{st.session_state['name']}_11_Blocks_Jathagam_Full_Report.txt",
        mime="text/plain",
        use_container_width=True
    )
    
    with st.expander("🔍 11 பிளாக்குகளையும் இங்கே விரிவாகப் படிக்கவும்", expanded=True):
        st.markdown(st.session_state["prediction_book"])

    # ==========================================
    # 💬 நேரடி கேள்வி-பதில் அரங்கம் (Live Q&A)
    # ==========================================
    st.divider()
    st.subheader("💬 ஜோதிடரிடம் நேரடிக் கேள்வி கேளுங்கள் (Live Q&A)")
    st.caption("தமிழ், English அல்லது Tanglish-ல் கேட்கலாம் (எ.கா: எனக்கு 2வது கல்யாணம் எப்போ நடக்கும்?)")
    
    user_q = st.text_input("உங்கள் கேள்வி:")
    if st.button("பதில் பெறுக"):
        if user_q:
            with st.spinner("⏳ சப்-லார்ட் மற்றும் தசா-புக்தியை ஆய்வு செய்கிறது..."):
                client = genai.Client(api_key=GEMINI_API_KEY)
                qa_prompt = f"""
ஜாதகர் தரவு & வாழ்நாள் தசா-புக்தி:
{st.session_state['chart_data']}

கேள்வி: "{user_q}"

விதிகள்:
எளிய தமிழில், நேரடி உண்மையை மட்டும் பேசவும் (No Sugarcoating). ஆட்சி/உச்ச பலம், மறுப்பு vs நிகழ்வு முறை தணிக்கை விதிகளைப் பின்பற்றி, சப்-லார்ட் & தசா-புக்தி அடிப்படையில் எப்போது நடக்கும் (Month/Year) எனக் கணித்து எளிய பரிகாரம் கூறுக.
"""
                try:
                    ans = client.models.generate_content(
                        model="gemini-2.5-flash", 
                        contents=qa_prompt,
                        config=types.GenerateContentConfig(system_instruction=SYSTEM_RULES)
                    )
                    st.write(ans.text)
                except Exception:
                    ans = client.models.generate_content(
                        model="gemini-1.5-flash", 
                        contents=qa_prompt,
                        config=types.GenerateContentConfig(system_instruction=SYSTEM_RULES)
                    )
                    st.write(ans.text)
