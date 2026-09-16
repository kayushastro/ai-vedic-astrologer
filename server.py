import json, math, datetime, os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
import swisseph as swe

CITIES = {"valsad": {"name": "Valsad, Gujarat", "lat": 20.61, "lon": 72.93}, "ahmedabad": {"name": "Ahmedabad, Gujarat", "lat": 23.0225, "lon": 72.5714}, "mumbai": {"name": "Mumbai, Maharashtra", "lat": 19.076, "lon": 72.8777}, "surat": {"name": "Surat, Gujarat", "lat": 21.1702, "lon": 72.8311}, "vadodara": {"name": "Vadodara, Gujarat", "lat": 22.3072, "lon": 73.1812}, "delhi": {"name": "Delhi", "lat": 28.6139, "lon": 77.209}, "jaipur": {"name": "Jaipur, Rajasthan", "lat": 26.9124, "lon": 75.7873}, "pune": {"name": "Pune, Maharashtra", "lat": 18.5204, "lon": 73.8567}, "bengaluru": {"name": "Bengaluru, Karnataka", "lat": 12.9716, "lon": 77.5946}, "hyderabad": {"name": "Hyderabad, Telangana", "lat": 17.385, "lon": 78.4867}, "chennai": {"name": "Chennai, Tamil Nadu", "lat": 13.0827, "lon": 80.2707}, "kolkata": {"name": "Kolkata, West Bengal", "lat": 22.5726, "lon": 88.3639}, "rajkot": {"name": "Rajkot, Gujarat", "lat": 22.3039, "lon": 70.8022}}
SIGNS = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
NAK = ["Ashwini","Bharani","Krittika","Rohini","Mrigashira","Ardra","Punarvasu","Pushya","Ashlesha","Magha","Purva Phalguni","Uttara Phalguni","Hasta","Chitra","Swati","Vishakha","Anuradha","Jyeshtha","Mula","Purva Ashadha","Uttara Ashadha","Shravana","Dhanishta","Shatabhisha","Purva Bhadrapada","Uttara Bhadrapada","Revati"]
PLANETS = [(swe.SUN,"Sun","Su"),(swe.MOON,"Moon","Mo"),(swe.MARS,"Mars","Ma"),(swe.MERCURY,"Mercury","Me"),(swe.JUPITER,"Jupiter","Ju"),(swe.VENUS,"Venus","Ve"),(swe.SATURN,"Saturn","Sa"),(swe.MEAN_NODE,"Rahu","Ra")]
# Ketu is opposite Rahu.
swe.set_sid_mode(swe.SIDM_LAHIRI)

def fmtdeg(x):
    d=int(x); m=int(round((x-d)*60))
    if m==60: d+=1; m=0
    return f"{d}Â° {m:02d}'"

def nakshatra(lon):
    idx=int((lon%360)/ (360/27))
    within=(lon%360)%(360/27)
    pada=int(within/(360/108))+1
    return NAK[idx],pada

def chart(req):
    if req.get("city") not in CITIES: raise ValueError("Please select a supported birth city.")
    if not req.get("dob") or not req.get("tob"): raise ValueError("Date and time are required.")
    y,m,d=map(int,req["dob"].split("-")); hh,mm=map(int,req["tob"].split(":"))
    # India Standard Time is UTC+5:30.
    utc=datetime.datetime(y,m,d,hh,mm)-datetime.timedelta(hours=5,minutes=30)
    hour=utc.hour+utc.minute/60+utc.second/3600
    jd=swe.julday(utc.year,utc.month,utc.day,hour)
    city=CITIES[req["city"]]
    flags=swe.FLG_SWIEPH|swe.FLG_SIDEREAL|swe.FLG_SPEED
    cusps,ascmc=swe.houses_ex(jd,city["lat"],city["lon"],b'P',flags)
    asc=ascmc[0]%360
    ayan=swe.get_ayanamsa_ut(jd)
    lagna_sign=int(asc//30)
    out=[]
    for pid,name,short in PLANETS:
        xx,rf,msg=swe.calc_ut(jd,pid,flags); lon=xx[0]%360
        sign=int(lon//30)
        house=((sign-lagna_sign)%12)+1
        nk,pada=nakshatra(lon)
        out.append({"name":name,"short":short,"sign":SIGNS[sign],"degree":fmtdeg(lon%30),"nakshatra":f"{nk} (Pada {pada})","house":house,"retrograde":xx[3]<0})
    # Ketu
    rahu=[p for p in out if p["name"]=="Rahu"][0]
    rahu_lon=None
    xx,_,msg=swe.calc_ut(jd,swe.MEAN_NODE,flags); rahu_lon=xx[0]%360
    ketu_lon=(rahu_lon+180)%360
    nk,pada=nakshatra(ketu_lon); sign=int(ketu_lon//30)
    out.append({"name":"Ketu","short":"Ke","sign":SIGNS[sign],"degree":fmtdeg(ketu_lon%30),"nakshatra":f"{nk} (Pada {pada})","house":((sign-lagna_sign)%12)+1,"retrograde":True})
    moon=next(p for p in out if p["name"]=="Moon")
    return {"name":req.get("name") or "Friend","lagna":{"sign":SIGNS[lagna_sign],"degree":fmtdeg(asc%30)},"moon":moon,"ayanamsa":ayan,"planets":out,"houses":[SIGNS[(lagna_sign+i)%12] for i in range(12)]}

class Handler(BaseHTTPRequestHandler):
    def send(self,code,body,ctype="text/html; charset=utf-8"):
        self.send_response(code); self.send_header("Content-Type",ctype); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if urlparse(self.path).path=="/":
            self.send(200, open("index.html", "rb").read())
        else: self.send(404,b"Not found","text/plain")
    def do_POST(self):
        if urlparse(self.path).path!="/api/chart": return self.send(404,b"Not found","text/plain")
        try:
            n=int(self.headers.get("Content-Length","0")); req=json.loads(self.rfile.read(n)); result=chart(req)
            self.send(200,json.dumps(result).encode(),"application/json; charset=utf-8")
        except Exception as e:
            self.send(400,json.dumps({"error":str(e)}).encode(),"application/json; charset=utf-8")

if __name__=="__main__":
    port=int(os.environ.get("PORT","8000"))
    host="0.0.0.0" if os.environ.get("PORT") else "127.0.0.1"
    print(f"AI Vedic Astrologer V2 running at http://{host}:{port}")
    print("Keep this window open while using the app.")
    HTTPServer((host,port),Handler).serve_forever()
