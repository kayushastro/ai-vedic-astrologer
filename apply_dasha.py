import re
import shutil

PATH = "index.html"
BACKUP = "index_before_dasha_upgrade.html"

with open(PATH, "r", encoding="utf-8") as f:
    html = f.read()

shutil.copy2(PATH, BACKUP)

helper = r"""
function calculateVimshottari(data){
  const nakshatras = [
    ["Ashwini","Ketu",7],["Bharani","Venus",20],["Krittika","Sun",6],
    ["Rohini","Moon",10],["Mrigashira","Mars",7],["Ardra","Rahu",18],
    ["Punarvasu","Jupiter",16],["Pushya","Saturn",19],["Ashlesha","Mercury",17],
    ["Magha","Ketu",7],["Purva Phalguni","Venus",20],["Uttara Phalguni","Sun",6],
    ["Hasta","Moon",10],["Chitra","Mars",7],["Swati","Rahu",18],
    ["Vishakha","Jupiter",16],["Anuradha","Saturn",19],["Jyeshtha","Mercury",17],
    ["Mula","Ketu",7],["Purva Ashadha","Venus",20],["Uttara Ashadha","Sun",6],
    ["Shravana","Moon",10],["Dhanishtha","Mars",7],["Shatabhisha","Rahu",18],
    ["Purva Bhadrapada","Jupiter",16],["Uttara Bhadrapada","Saturn",19],
    ["Revati","Mercury",17]
  ];

  const order = ["Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury"];
  const years = {Ketu:7,Venus:20,Sun:6,Moon:10,Mars:7,Rahu:18,Jupiter:16,Saturn:19,Mercury:17};
  const signs = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"];

  const signIndex = signs.indexOf(data.moon.sign);
  const dm = (data.moon.degree || "0 0").match(/\d+/g) || ["0","0"];
  const degree = Number(dm[0] || 0) + Number(dm[1] || 0) / 60;
  const moonLon = signIndex * 30 + degree;

  const nakSize = 13 + 20/60;
  const nakIndex = Math.min(26, Math.floor(moonLon / nakSize));
  const nak = nakshatras[nakIndex];
  const traversed = Math.max(0, Math.min(1, (moonLon - nakIndex * nakSize) / nakSize));

  const startLord = nak[1];
  const startIndex = order.indexOf(startLord);

  const parts = (data.dob || "2000-01-01").split("-").map(Number);
  const tm = (data.tob || "00:00").split(":").map(Number);
  const birth = new Date(Date.UTC(parts[0], parts[1]-1, parts[2], tm[0] || 0, tm[1] || 0));
  const yearMs = 365.2425 * 86400000;

  function addYears(date, y){
    return new Date(date.getTime() + y * yearMs);
  }

  function fmt(date){
    return date.toLocaleDateString(undefined, {day:"2-digit", month:"short", year:"numeric"});
  }

  const periods = [];
  let cursor = new Date(birth);

  for(let i=0; i<9; i++){
    const lord = order[(startIndex + i) % 9];
    const fullYears = years[lord];
    const actualYears = i === 0 ? fullYears * (1 - traversed) : fullYears;
    const end = addYears(cursor, actualYears);
    const antars = [];
    let ac = new Date(cursor);
    const lordIndex = order.indexOf(lord);

    for(let j=0; j<9; j++){
      const antarLord = order[(lordIndex + j) % 9];
      const antarYears = actualYears * years[antarLord] / 120;
      const antarEnd = addYears(ac, antarYears);
      antars.push({lord:antarLord, start:new Date(ac), end:antarEnd, years:antarYears});
      ac = antarEnd;
    }

    periods.push({lord:lord, start:new Date(cursor), end:end, antars:antars});
    cursor = end;
  }

  const now = new Date();
  let currentMaha = null;
  let currentAntar = null;

  for(const m of periods){
    if(now >= m.start && now < m.end){
      currentMaha = m;
      currentAntar = m.antars.find(a => now >= a.start && now < a.end) || null;
      break;
    }
  }

  return {nak:nak, startLord:startLord, periods:periods, currentMaha:currentMaha, currentAntar:currentAntar, fmt:fmt};
}

function premiumDashaHTML(data){
  const d = calculateVimshottari(data);
  const planets = data.planets || [];
  const find = n => planets.find(x => x.name === n);
  const planetText = n => {
    const x = find(n);
    return x ? x.sign + " — House " + x.house : "Not available";
  };

  const cm = d.currentMaha;
  const ca = d.currentAntar;

  const themes = {
    Ketu:"detachment, restructuring, research and major internal shifts",
    Venus:"relationships, comforts, creativity, networks, agreements and material gains",
    Sun:"leadership, authority, visibility, identity and responsibility",
    Moon:"mind, family, public interaction, emotional priorities and changing circumstances",
    Mars:"action, competition, courage, property, initiative and decisive effort",
    Rahu:"foreign links, unconventional opportunities, ambition, technology and sudden changes",
    Jupiter:"learning, expansion, guidance, finance, children and broader opportunities",
    Saturn:"discipline, responsibility, long-term work, persistence and restructuring",
    Mercury:"business, communication, analysis, commerce, contracts and learning"
  };

  let timeline = [];
  if(cm){
    for(const a of cm.antars){
      if(a.end > new Date()) timeline.push({type:"Antardasha", lord:a.lord, start:a.start, end:a.end});
    }
    const idx = d.periods.indexOf(cm);
    for(let i=1; i<4 && idx+i<d.periods.length; i++){
      const m = d.periods[idx+i];
      timeline.push({type:"Mahadasha", lord:m.lord, start:m.start, end:m.end});
    }
  }

  const rows = timeline.slice(0,8).map(x =>
    "<tr><td><b>"+x.type+"</b></td><td>"+x.lord+"</td><td>"+d.fmt(x.start)+"</td><td>"+d.fmt(x.end)+"</td></tr>"
  ).join("");

  return `
  <div class="card premium">
    <h2>&#8377;199 Premium Vedic Report</h2>
    <p><b>Personalized Vimshottari Dasha & Timing Analysis for ${data.name}</b></p>
    <p class="muted">Calculated from the Moon's birth nakshatra using the traditional 120-year Vimshottari Dasha sequence.</p>

    <h3>&#128197; 1. Vimshottari Dasha Foundation</h3>
    <p>Your Moon is in <b>${data.moon.nakshatra}</b>. The Dasha sequence begins from <b>${d.startLord}</b>, with the first Mahadasha balance adjusted for the portion of the nakshatra already elapsed at birth.</p>

    ${cm ? `
    <h3>&#9200; 2. Current Mahadasha</h3>
    <p><b>${cm.lord} Mahadasha</b><br>${d.fmt(cm.start)} to ${d.fmt(cm.end)}</p>
    <p>This period traditionally emphasizes <b>${themes[cm.lord]}</b>. In your chart, ${cm.lord} is placed in <b>${planetText(cm.lord)}</b>, so its interpretation should be connected to that house and sign.</p>
    ` : ""}

    ${ca ? `
    <h3>&#128337; 3. Current Antardasha</h3>
    <p><b>${cm.lord} / ${ca.lord}</b><br>${d.fmt(ca.start)} to ${d.fmt(ca.end)}</p>
    <p>The ${ca.lord} sub-period adds themes of <b>${themes[ca.lord]}</b>. The Mahadasha and Antardasha together provide the principal timing layer in this report.</p>
    ` : ""}

    <h3>&#128200; 4. Upcoming Dasha Timeline</h3>
    <table class="chart">
      <thead><tr><th>Period</th><th>Lord</th><th>Start</th><th>End</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>

    <h3>&#128188; 5. Career & Business Timing</h3>
    <p>Your 10th house is <b>${data.houses[9]}</b>. Career timing is traditionally assessed through the 10th house, its lord and the active Dasha planets together. Dasha periods can show when professional themes become more prominent, while actual outcomes also depend on decisions and circumstances.</p>

    <h3>&#128176; 6. Money & Wealth Timing</h3>
    <p>Your 2nd house is <b>${data.houses[1]}</b> and your 11th house is <b>${data.houses[10]}</b>. Financial timing is traditionally examined by activating their lords and supporting planets through Mahadasha and Antardasha.</p>

    <h3>&#10084;&#65039; 7. Marriage & Relationship Timing</h3>
    <p>Your 7th house is <b>${data.houses[6]}</b>. Relationship timing traditionally considers the 7th lord, Venus and Dasha activation. These periods can be examined for greater relationship emphasis without treating timing as a certainty.</p>

    <h3>&#127793; 8. Personal Growth & Major Life Themes</h3>
    <p>The active Dasha describes the broader developmental theme of a period. Your ${cm ? cm.lord : "current"} influence should be considered alongside your ${data.lagna.sign} Ascendant and ${data.moon.sign} Moon.</p>

    <h3>&#128202; 9. Planetary Dasha Reference</h3>
    <p>
      <b>Sun:</b> ${planetText("Sun")}<br>
      <b>Moon:</b> ${planetText("Moon")}<br>
      <b>Mars:</b> ${planetText("Mars")}<br>
      <b>Mercury:</b> ${planetText("Mercury")}<br>
      <b>Jupiter:</b> ${planetText("Jupiter")}<br>
      <b>Venus:</b> ${planetText("Venus")}<br>
      <b>Saturn:</b> ${planetText("Saturn")}<br>
      <b>Rahu:</b> ${planetText("Rahu")}<br>
      <b>Ketu:</b> ${planetText("Ketu")}
    </p>

    <h3>&#11088; 10. Premium Timing Summary</h3>
    <p>
      <b>Birth Nakshatra:</b> ${d.nak[0]}<br>
      <b>Starting Dasha Lord:</b> ${d.startLord}<br>
      <b>Current Mahadasha:</b> ${cm ? cm.lord : "Calculating"}<br>
      <b>Current Antardasha:</b> ${ca ? ca.lord : "Calculating"}<br>
      ${cm ? "<b>Current Mahadasha ends:</b> "+d.fmt(cm.end)+"<br><b>Current Antardasha ends:</b> "+d.fmt(ca.end) : ""}
    </p>

    <p class="muted">Astrological timing is a traditional interpretive system, not a guarantee of future events. Use this report as reflective guidance alongside real-world information and decisions.</p>
  </div>`;
}
"""

if "function calculateVimshottari" not in html:
    marker = "function showPremiumOptions(){"
    if marker not in html:
        raise SystemExit("Could not find showPremiumOptions() in index.html")
    html = html.replace(marker, helper + "\n" + marker, 1)

start = html.find('if(choice === "3")')
if start == -1:
    raise SystemExit('Could not find Premium option 3 branch.')

brace = html.find("{", start)
if brace == -1:
    raise SystemExit("Could not find Premium option 3 opening brace.")

depth = 0
end = -1
for i in range(brace, len(html)):
    if html[i] == "{":
        depth += 1
    elif html[i] == "}":
        depth -= 1
        if depth == 0:
            end = i + 1
            break

if end == -1:
    raise SystemExit("Could not locate Premium option 3 closing brace.")

replacement = 'if(choice === "3"){ const r=document.getElementById("reading"); r.innerHTML += premiumDashaHTML(currentData); r.scrollIntoView({behavior:"smooth"}); }'
html = html[:start] + replacement + html[end:]

with open(PATH, "w", encoding="utf-8") as f:
    f.write(html)

scripts_open = len(re.findall(r"<script>", html))
scripts_close = len(re.findall(r"</script>", html))
if scripts_open != scripts_close:
    shutil.copy2(BACKUP, PATH)
    raise SystemExit("Script tag count mismatch; restored backup.")

print("Dasha helper:", "function calculateVimshottari" in html)
print("Premium option 3:", "premiumDashaHTML(currentData)" in html)
print("Broken h3 headings:", len(re.findall(r"<h3>\?+", html)))
print("Script tags:", scripts_open, scripts_close)
print("Backup:", BACKUP)
