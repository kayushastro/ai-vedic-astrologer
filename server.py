import json, math, datetime, os
import base64
import hashlib
import hmac
import urllib.request
import urllib.error
from zoneinfo import ZoneInfo
import worldcities
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import swisseph as swe

# ---------------------------------------------------------
# Razorpay configuration
# Secrets are supplied through environment variables.
# Never place the secret in index.html or GitHub.
# ---------------------------------------------------------

RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "").strip()
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "").strip()
RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "").strip()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.6-luna").strip() or "gpt-5.6-luna"

REPORT_PRICES = {
    "quick": 4900,
    "complete": 9900,
    "premium": 19900,
}

REPORT_NAMES = {
    "quick": "NAKSHIRA Quick Report",
    "complete": "NAKSHIRA Complete Report",
    "premium": "NAKSHIRA Premium Report",
}


def razorpay_auth_header():
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        raise ValueError("Razorpay credentials are not configured on the server.")

    token = base64.b64encode(
        f"{RAZORPAY_KEY_ID}:{RAZORPAY_KEY_SECRET}".encode("utf-8")
    ).decode("ascii")

    return "Basic " + token


def razorpay_request(method, endpoint, payload=None):
    url = "https://api.razorpay.com/v1" + endpoint

    data = None
    headers = {
        "Authorization": razorpay_auth_header(),
        "Content-Type": "application/json",
        "User-Agent": "NAKSHIRA/1.0",
    }

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw)

    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(raw)
        except Exception:
            detail = {"error": raw}

        raise ValueError(
            "Razorpay API error: " + json.dumps(detail, ensure_ascii=False)
        )


def create_razorpay_order(report_type):
    if report_type not in REPORT_PRICES:
        raise ValueError("Invalid report type.")

    amount = REPORT_PRICES[report_type]

    order = razorpay_request(
        "POST",
        "/orders",
        {
            "amount": amount,
            "currency": "INR",
            "receipt": "nakshira_" + report_type + "_" + datetime.datetime.now(
                datetime.timezone.utc
            ).strftime("%Y%m%d%H%M%S"),
            "notes": {
                "product": REPORT_NAMES[report_type],
                "report_type": report_type,
            },
        },
    )

    return {
        "order_id": order["id"],
        "amount": order["amount"],
        "currency": order["currency"],
        "key_id": RAZORPAY_KEY_ID,
        "report_type": report_type,
        "report_name": REPORT_NAMES[report_type],
    }


def verify_razorpay_webhook_signature(body, signature):
    if not RAZORPAY_WEBHOOK_SECRET or not signature:
        return False

    expected = hmac.new(
        RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
        body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


def verify_razorpay_payment(order_id, payment_id, signature, report_type):
    if not order_id or not payment_id or not signature:
        raise ValueError("Payment verification data is incomplete.")

    if report_type not in REPORT_PRICES:
        raise ValueError("Invalid report type.")

    # Verify Razorpay's checkout signature.
    message = f"{order_id}|{payment_id}".encode("utf-8")

    expected = hmac.new(
        RAZORPAY_KEY_SECRET.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise ValueError("Payment signature verification failed.")

    # Retrieve the order from Razorpay rather than trusting the browser.
    order = razorpay_request("GET", "/orders/" + order_id)

    expected_amount = REPORT_PRICES[report_type]

    if int(order.get("amount", 0)) != expected_amount:
        raise ValueError("Payment amount does not match the selected report.")

    if order.get("currency") != "INR":
        raise ValueError("Unexpected payment currency.")

    # Retrieve payment status from Razorpay.
    payment = razorpay_request("GET", "/payments/" + payment_id)

    if payment.get("order_id") != order_id:
        raise ValueError("Payment does not belong to this order.")

    if int(payment.get("amount", 0)) != expected_amount:
        raise ValueError("Payment amount verification failed.")

    if payment.get("currency") != "INR":
        raise ValueError("Unexpected payment currency.")

    if payment.get("status") != "captured":
        raise ValueError(
            "Payment has not been captured yet. Current status: "
            + str(payment.get("status"))
        )

    return {
        "verified": True,
        "report_type": report_type,
        "report_name": REPORT_NAMES[report_type],
        "order_id": order_id,
        "payment_id": payment_id,
    }


CITIES = {"valsad": {"name": "Valsad, Gujarat", "lat": 20.61, "lon": 72.93, "timezone": "Asia/Kolkata"}, "ahmedabad": {"name": "Ahmedabad, Gujarat", "lat": 23.0225, "lon": 72.5714, "timezone": "Asia/Kolkata"}, "mumbai": {"name": "Mumbai, Maharashtra", "lat": 19.076, "lon": 72.8777, "timezone": "Asia/Kolkata"}, "surat": {"name": "Surat, Gujarat", "lat": 21.1702, "lon": 72.8311, "timezone": "Asia/Kolkata"}, "vadodara": {"name": "Vadodara, Gujarat", "lat": 22.3072, "lon": 73.1812, "timezone": "Asia/Kolkata"}, "delhi": {"name": "Delhi", "lat": 28.6139, "lon": 77.209, "timezone": "Asia/Kolkata"}, "jaipur": {"name": "Jaipur, Rajasthan", "lat": 26.9124, "lon": 75.7873, "timezone": "Asia/Kolkata"}, "pune": {"name": "Pune, Maharashtra", "lat": 18.5204, "lon": 73.8567, "timezone": "Asia/Kolkata"}, "bengaluru": {"name": "Bengaluru, Karnataka", "lat": 12.9716, "lon": 77.5946, "timezone": "Asia/Kolkata"}, "hyderabad": {"name": "Hyderabad, Telangana", "lat": 17.385, "lon": 78.4867, "timezone": "Asia/Kolkata"}, "chennai": {"name": "Chennai, Tamil Nadu", "lat": 13.0827, "lon": 80.2707, "timezone": "Asia/Kolkata"}, "kolkata": {"name": "Kolkata, West Bengal", "lat": 22.5726, "lon": 88.3639, "timezone": "Asia/Kolkata"}, "rajkot": {"name": "Rajkot, Gujarat", "lat": 22.3039, "lon": 70.8022, "timezone": "Asia/Kolkata"}}
SIGNS = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
NAK = ["Ashwini","Bharani","Krittika","Rohini","Mrigashira","Ardra","Punarvasu","Pushya","Ashlesha","Magha","Purva Phalguni","Uttara Phalguni","Hasta","Chitra","Swati","Vishakha","Anuradha","Jyeshtha","Mula","Purva Ashadha","Uttara Ashadha","Shravana","Dhanishta","Shatabhisha","Purva Bhadrapada","Uttara Bhadrapada","Revati"]
PLANETS = [(swe.SUN,"Sun","Su"),(swe.MOON,"Moon","Mo"),(swe.MARS,"Mars","Ma"),(swe.MERCURY,"Mercury","Me"),(swe.JUPITER,"Jupiter","Ju"),(swe.VENUS,"Venus","Ve"),(swe.SATURN,"Saturn","Sa"),(swe.MEAN_NODE,"Rahu","Ra")]
# Ketu is opposite Rahu.
swe.set_sid_mode(swe.SIDM_LAHIRI)

def fmtdeg(x):
    d=int(x); m=int(round((x-d)*60))
    if m==60: d+=1; m=0
    return f"{d}° {m:02d}'"

def nakshatra(lon):
    idx=int((lon%360)/ (360/27))
    within=(lon%360)%(360/27)
    pada=int(within/(360/108))+1
    return NAK[idx],pada

def openai_ai_chat(question, chart_data, history):
    if not OPENAI_API_KEY:
        raise ValueError("AI chat is not configured yet. Add OPENAI_API_KEY in Railway variables.")
    question=str(question or "").strip()
    if not question: raise ValueError("Please enter a question.")
    if len(question)>1200: raise ValueError("Please keep your question under 1200 characters.")
    if not isinstance(chart_data,dict): raise ValueError("Chart data is required. Please calculate the birth chart first.")
    hist=history if isinstance(history,list) else []
    hist=hist[-8:]
    cj=json.dumps(chart_data,ensure_ascii=False,separators=(",",":"))
    lines=[]
    for x in hist:
        if isinstance(x,dict) and str(x.get("role","")).lower() in ("user","assistant"):
            lines.append(str(x.get("role","")).upper()+": "+str(x.get("content",""))[:2000])
    ins=("You are NAKSHIRA AI, a chart-aware Vedic astrology assistant. Use only the supplied calculated sidereal Vedic chart for chart facts. Interpret using traditional Vedic astrology principles and distinguish interpretation from certainty. Never invent placements, houses, nakshatras, dashas, transits or birth details. If required data is missing, say so. For medical, legal or financial matters, give general information and do not present astrology as a substitute for qualified professional advice. Be warm, concise, practical and personalized.")
    prompt="BIRTH CHART DATA:\n"+cj+"\n\nRECENT CHAT:\n"+("\n".join(lines) or "(none)")+"\n\nUSER QUESTION:\n"+question
    payload={"model":OPENAI_MODEL,"instructions":ins,"input":prompt,"reasoning":{"effort":"low"},"max_output_tokens":700}
    req=urllib.request.Request("https://api.openai.com/v1/responses",data=json.dumps(payload).encode(),headers={"Content-Type":"application/json","Authorization":"Bearer "+OPENAI_API_KEY},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=60) as r: data=json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ValueError("AI provider error: "+e.read().decode("utf-8",errors="replace")[:1000])
    except urllib.error.URLError as e: raise ValueError("AI provider connection failed: "+str(e))
    if data.get("error"): raise ValueError("AI provider error: "+str(data["error"])[:1000])
    answer=str(data.get("output_text","")).strip()
    if not answer:
        parts=[]
        for item in data.get("output",[]):
            for c in item.get("content",[]) if isinstance(item,dict) else []:
                if isinstance(c,dict) and c.get("type")=="output_text": parts.append(str(c.get("text","")))
        answer="\n".join(parts).strip()
    if not answer: raise ValueError("AI provider returned an empty response.")
    return {"ok":True,"answer":answer,"model":OPENAI_MODEL}

def chart(req):
    city_key=req.get("city")
    if city_key in CITIES:
        city=CITIES[city_key]
    elif city_key in worldcities.CITIES:
        wc=worldcities.CITIES[city_key]
        city={"name":f'{wc["name"]}, {wc["country"]}',"lat":wc["lat"],"lon":wc["lon"],"timezone":wc["timezone"]}
    else:
        raise ValueError("Please select a valid birth city from the search results.")
    if not req.get("dob") or not req.get("tob"): raise ValueError("Date and time are required.")
    y,m,d=map(int,req["dob"].split("-")); hh,mm=map(int,req["tob"].split(":"))
    local_dt=datetime.datetime(y,m,d,hh,mm,tzinfo=ZoneInfo(city["timezone"]))
    utc=local_dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    hour=utc.hour+utc.minute/60+utc.second/3600
    jd=swe.julday(utc.year,utc.month,utc.day,hour)
    local_dt=datetime.datetime(y,m,d,hh,mm,tzinfo=ZoneInfo(city["timezone"]))
    utc=local_dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    hour=utc.hour+utc.minute/60+utc.second/3600
    jd=swe.julday(utc.year,utc.month,utc.day,hour)
    
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
        self.send_response(code)
        self.send_header("Content-Type",ctype)
        self.send_header("Cache-Control","no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path=urlparse(self.path).path

        if path=="/":
            self.send(200, open("index.html", "rb").read())
            return

        if path=="/api/cities":
            try:
                query=parse_qs(urlparse(self.path).query).get("q",[""])[0]
                results=worldcities.search_cities(query,10)

                output=[]
                for city in results:
                    output.append({
                        "id":city["id"],
                        "name":city["name"],
                        "country":city["country"],
                        "lat":city["lat"],
                        "lon":city["lon"],
                        "timezone":city["timezone"],
                        "population":city["population"]
                    })

                self.send(
                    200,
                    json.dumps(output,ensure_ascii=False).encode("utf-8"),
                    "application/json; charset=utf-8"
                )
            except Exception as e:
                self.send(
                    400,
                    json.dumps({"error":str(e)}).encode("utf-8"),
                    "application/json; charset=utf-8"
                )
            return

        # -------------------------------------------------
        # Razorpay webhook
        # -------------------------------------------------
        if path == "/api/razorpay-webhook":
            try:
                n = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(n)
                signature = self.headers.get(
                    "X-Razorpay-Signature", ""
                ).strip()

                if not verify_razorpay_webhook_signature(
                    body, signature
                ):
                    self.send(
                        400,
                        json.dumps({
                            "ok": False,
                            "error": "Invalid webhook signature"
                        }).encode(),
                        "application/json; charset=utf-8"
                    )
                    return

                event = json.loads(body.decode("utf-8"))
                event_name = str(
                    event.get("event", "")
                ).strip()

                print(
                    "Razorpay webhook received:",
                    event_name
                )

                self.send(
                    200,
                    json.dumps({
                        "ok": True,
                        "event": event_name
                    }).encode(),
                    "application/json; charset=utf-8"
                )

            except Exception as e:
                self.send(
                    400,
                    json.dumps({
                        "ok": False,
                        "error": str(e)
                    }).encode(),
                    "application/json; charset=utf-8"
                )

            return

        self.send(404,b"Not found","text/plain")

    def do_POST(self):
        path = urlparse(self.path).path

        # -------------------------------------------------
        # NAKSHIRA AI chat endpoint
        # -------------------------------------------------
        if path == "/api/ai-chat":
            try:
                n = int(self.headers.get("Content-Length", "0"))
                req = json.loads(self.rfile.read(n))
                result = openai_ai_chat(
                    req.get("question", ""),
                    req.get("chart_data", {}),
                    req.get("history", []),
                )
                self.send(
                    200,
                    json.dumps(result, ensure_ascii=False).encode("utf-8"),
                    "application/json; charset=utf-8"
                )
            except Exception as e:
                self.send(
                    400,
                    json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False).encode("utf-8"),
                    "application/json; charset=utf-8"
                )
            return

        # -------------------------------------------------
        # Existing astrology chart endpoint
        # -------------------------------------------------
        if path == "/api/chart":
            try:
                n = int(self.headers.get("Content-Length", "0"))
                req = json.loads(self.rfile.read(n))
                result = chart(req)

                self.send(
                    200,
                    json.dumps(result).encode(),
                    "application/json; charset=utf-8"
                )

            except Exception as e:
                self.send(
                    400,
                    json.dumps({"error": str(e)}).encode(),
                    "application/json; charset=utf-8"
                )

            return

        # -------------------------------------------------
        # Create Razorpay order
        # -------------------------------------------------
        if path == "/api/create-order":
            try:
                n = int(self.headers.get("Content-Length", "0"))
                req = json.loads(self.rfile.read(n))

                report_type = str(req.get("report_type", "")).strip().lower()

                result = create_razorpay_order(report_type)

                self.send(
                    200,
                    json.dumps(result).encode(),
                    "application/json; charset=utf-8"
                )

            except Exception as e:
                self.send(
                    400,
                    json.dumps({"error": str(e)}).encode(),
                    "application/json; charset=utf-8"
                )

            return

        # -------------------------------------------------
        # Verify Razorpay payment
        # -------------------------------------------------
        if path == "/api/verify-payment":
            try:
                n = int(self.headers.get("Content-Length", "0"))
                req = json.loads(self.rfile.read(n))

                result = verify_razorpay_payment(
                    str(req.get("razorpay_order_id", "")).strip(),
                    str(req.get("razorpay_payment_id", "")).strip(),
                    str(req.get("razorpay_signature", "")).strip(),
                    str(req.get("report_type", "")).strip().lower(),
                )

                self.send(
                    200,
                    json.dumps(result).encode(),
                    "application/json; charset=utf-8"
                )

            except Exception as e:
                self.send(
                    400,
                    json.dumps({
                        "verified": False,
                        "error": str(e)
                    }).encode(),
                    "application/json; charset=utf-8"
                )

            return

        self.send(404, b"Not found", "text/plain")

if __name__=="__main__":
    port=int(os.environ.get("PORT","8000"))
    host="0.0.0.0" if os.environ.get("PORT") else "127.0.0.1"
    print(f"AI Vedic Astrologer V2 running at http://{host}:{port}")
    print("Keep this window open while using the app.")
    HTTPServer((host,port),Handler).serve_forever()

