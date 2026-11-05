# The E20 water-ingress website, explained in plain language

A guide to presenting every part of the site to a non-specialist audience (or a review panel).
Each section below matches one chapter of the website, in the same order. For each one you get:

- **What you see**: what is on the screen
- **What it means**: the plain-language explanation
- **Say it like this**: a short script you can use while presenting
- **If someone asks**: likely questions and honest answers

At the end there is a glossary, a one-minute summary, and a list of what we must *not* claim.

---

## 0. The big idea in 30 seconds

India is moving from E10 petrol (10 % ethanol) to **E20 (20 % ethanol)**. Ethanol loves water. A
little water is absorbed into the fuel and is harmless, but once the fuel has taken in more water
than it can hold, the mixture **splits into two layers**: a petrol layer on top and a heavy
ethanol–water layer at the bottom. That bottom layer sits right where the pump sucks fuel from, so
customers can get water-rich fuel in their engines, and the petrol left on top has lost its ethanol
(lower octane).

Our project is an **early-warning system** with two layers:

| | Where | What it does | Data used |
|---|---|---|---|
| **Layer A** | Fuel depot | Scans a sample from every tanker with a light-based instrument (spectrometer) and checks the ethanol content in seconds: PASS / REVIEW / FAIL | **Real** fuel measurements |
| **Layer B** | Petrol pump's underground tank | Uses the tank's sensors and the weather forecast to predict, 1–3 days ahead, whether the tank is heading for separation: SAFE / WATCH / ACT | **Simulated** tanks driven by **real** weather |

**Say it like this:** "Layer A stops bad fuel before it leaves the depot. Layer B watches every
petrol-pump tank afterwards and warns the station a day or two before water becomes a problem."

---

## How to read the coloured labels on the site

Every number and chart on the site carries a label. This is the honesty system of the project and
is worth explaining at the start of any presentation.

| Label | Meaning in plain words |
|---|---|
| **REAL DATA** | Measured on real samples by someone else and published openly. We did not make it up. |
| **REAL DATA (ERA5 reanalysis)** | Real historical weather (temperature, humidity, rain) for Indian cities, from the European weather agency's archive. |
| **LITERATURE VALUE** | A number taken from a published paper, patent or standard. |
| **STANDARD** | A legal/official limit (Bureau of Indian Standards, European standard). |
| **SYNTHETIC (physics-informed)** | Produced by our own computer simulation. It follows real physics but is **not** a field measurement. |
| **ASSUMPTION** | A value we had to guess (e.g. how big a leak is). Clearly marked; needs checking with real data. |

**Say it like this:** "Every number on this site tells you where it came from. 'Real data'
is measured, 'synthetic' is our simulation, and 'assumption' means we had to estimate it."

---

## The top of the page (hero)

**What you see:** The title "Keeping water out of E20", an animated circle showing a tank with water
droplets sinking into a bottom layer, and three big numbers.

**The three numbers:**

1. **±0.9 % ethanol error (REAL DATA).** When our model reads the ethanol content of a real fuel
   sample from its spectrum, it is typically off by about 0.9 percentage points. If the true value is
   10 %, we would usually say something between about 9.1 % and 10.9 %.
2. **1.7–1.8 wt % (LITERATURE VALUE).** At 20 °C, E20 can hold about 1.75 % water by weight before it
   splits. That is roughly **26 times** the official quality limit for water in E20. So "off-spec"
   and "separated" are two very different things.
3. **~42 hours warning (SYNTHETIC).** In our simulated tanks, the forecasting model warned about
   separation a median of about 42 hours in advance, catching 16 of 20 separation events.

**Say it like this:** "Three numbers sum up the project: we can read ethanol to within about one
percent from a ten-second scan; E20 can only hold under 2 % water before it splits; and in
simulation we can warn a pump about a day and a half before it happens."

---

## Chapter 1 · The problem: "A tank that breathes"

**What you see:** A cross-section of an underground fuel tank (fill cap, vent pipe, fuel, the air
space above the fuel). As you scroll, it animates through a real monsoon period (Varanasi, 2024).
A small chart below shows two lines: **blue = water in the tank**, **green = the most water the fuel
can hold**. Three tiles show water from humid air today, water from rain today, and the "margin to
separation".

**The five scroll steps, explained:**

1. **Underground.** The fuel sits at soil temperature. The empty space above it connects to the
   outside air through a vent pipe.
2. **Breathing.** Every cool night, and every litre sold, sucks a little outside air into the tank.
   Humid monsoon air carries water vapour. This adds only grams of water a day: harmless by itself.
3. **A leaking cap.** If the fill-cap seal is worn, rain runs straight in. One storm can add
   *kilograms* of water, which sinks to the bottom.
4. **The limit.** When the blue line (water present) crosses the green line (water the fuel can
   hold), the extra water separates out as a new layer.
5. **The cost.** That layer pulls ethanol out of the fuel and sits at the pump inlet. Our aim is to
   see it coming **24–48 hours ahead**.

**Margin to separation**, the single most important idea in Layer B:

> margin = 1 − (water in the tank ÷ water the fuel can hold)

- 100 % margin: the tank is completely dry
- 50 %: the tank holds half the water it could tolerate
- 0 % or below: the fuel has separated

Think of it like a fuel gauge, but for "how much more water can this tank take".

**Note:** The bottom layers are drawn 12× taller than real so you can see them (stated on the figure).

**Say it like this:** "Underground tanks breathe. Humid air adds a little water; a leaking cap in a
monsoon adds a lot. The fuel absorbs it up to a point, and then suddenly a water–ethanol layer forms
at the bottom, right where the pump draws fuel."

**If someone asks:**
- *"Is this a real tank?"* No. It is our simulated tank, but the weather driving it is the real
  recorded weather for Varanasi in June–July 2024.
- *"Isn't breathing the main problem?"* No. Our simulation, and the US EPA, both say breathing alone
  adds too little water. Liquid water (leaks, wet tankers) is what causes separation.

---

## Chapter 2 · The supply chain: "Four ways in"

**What you see:** A line of five stages (Distillery → Road tanker → Depot → Retail tank → Vehicle)
with four numbered blue circles showing where water gets in. Layer A is placed at the depot;
Layer B and "Solution 4" are at the retail tank.

**The four entry points:**

1. **Wet tanker:** water left in a tanker from cleaning or a previous load.
2. **Transfers:** India has no dedicated ethanol pipeline, so ethanol is moved by road many times,
   and each transfer is a chance for contamination.
3. **Breathing:** humid air through the tank vent.
4. **Bad seals:** rain entering through a worn fill cap or manhole.

**Say it like this:** "Water can get in at four points. We put one check at the depot, which catches
the first two, and a monitor on every pump tank, which catches the last two."

---

## Chapter 3 · Phase separation: "How much water is too much?"

**What you see:** Two big numbers, a warning box, and an interactive chart with a dashed line you
can drag up and down.

**The two limits (people often confuse them):**

| Limit | Value | What it means | Source |
|---|---|---|---|
| **Quality limit** | 0.05 % by volume (≈ 665 mg/kg) | Above this, the fuel is officially "off-spec", but still a single clear liquid | IS 17943:2022 |
| **Separation point** | ≈ 1.75 % by weight at 20 °C | Above this, the fuel physically splits into two layers | US patent 8,268,629 correlation |

These are about **26× apart**.

**The warning box:** The original project used **0.5 % (5,000 ppm)** as "the water limit". That
number is actually the limit for water in **pure ethanol before it is blended** (IS 15464). It is
not the limit for E20. We corrected this and keep all three numbers separate.

**The interactive chart:**
- X-axis: fuel temperature (−20 °C to 45 °C). Y-axis: water content.
- **Solid blue line:** how much water E20 can hold at each temperature. It slopes **up**: warm fuel
  holds more water and cold fuel holds less.
- **Faded dashed blue line:** the same curve for E10. It is lower, so E10 tolerates less water.
- **Green flat line:** the quality limit, near the bottom.
- **Orange dots:** real measurements from published studies (EPA 1995 for E10, Haq & Ali 1990 for
  E25), used to check the curve.
- **Drag the black dashed line** to set how much water is in the tank. The orange shaded zone shows
  the temperatures at which that fuel would separate. The tiles tell you the exact temperature.

**Key insight:** Separation can be triggered by **cooling**, not just by adding water. A tank that
is fine on a hot afternoon can separate on a cold night with the same amount of water inside.

**Say it like this:** "There are two limits. The quality limit is tiny; above it the fuel is
technically off-spec. The separation limit is about 26 times higher; above it the fuel physically
splits. And because colder fuel holds less water, a tank can separate simply because the weather
turned cold."

---

## Chapter 4 · Layer A: "Check every tanker"

**What you see:** A note on Raman vs NIR, then a step-by-step animated figure of how a spectrum
becomes a decision, then the results.

### What is a spectrum? (simple version)

Shine a laser at the fuel. Molecules vibrate and scatter back a tiny amount of light at slightly
shifted colours. Each type of molecule (ethanol, benzene, ethers…) has its own pattern of peaks,
like a fingerprint. The plot of those peaks is the **Raman spectrum**. The instrument is handheld
and a scan takes about ten seconds.

### "Raman, not NIR"

Our original proposal said NIR (near-infrared). The only public dataset of real fuels with lab
reference values is **Raman** (179 real petrol samples, handheld 785 nm instrument, published by a
German university on Hugging Face). Both are "light fingerprint" methods and are calibrated the same
way, so the method carries over. We did not pretend the Raman data was NIR.

### The six steps (scroll through them on the site)

1. **Raw spectrum.** The peaks are molecular vibrations. The broad hump underneath is
   *fluorescence*, a glow that is not useful information.
2. **Crop.** Keep only the useful window (400–1800 cm⁻¹). Water's signature band (~3400 cm⁻¹) is
   outside this instrument's range, which is why water can't be measured well (see below).
3. **Remove baseline.** Fit a smooth curve under the spectrum and subtract it, removing the
   fluorescence hump.
4. **Normalise.** Rescale each spectrum so the laser power or focus doesn't matter, only the shape.
5. **Project.** The model (PLS, explained below) squeezes the 1,401 numbers in the spectrum into 5
   summary scores. The scatter plot shows all training samples as dots (darker = more ethanol) and
   the current sample circled. If a sample lands far from the cloud, it is unlike anything the model
   has seen, so it is flagged for review.
6. **Decide.** The model gives a value **with an error bar**. Rule:
   - **PASS:** the whole error bar is inside the allowed range
   - **FAIL:** the whole error bar is outside
   - **REVIEW:** the error bar straddles the limit, so send it to the lab

**What is PLS?** (Partial Least Squares regression.) A standard statistical method for turning a
spectrum into a number. It finds the few combinations of peaks that best track the ethanol content.
It's the industry standard for this kind of instrument, and it is simple and explainable.

### "How well does it work?" (results block)

Scored **once** on 36 samples the model never saw while being built:

| Number | Value | Plain meaning |
|---|---|---|
| R² | 0.95 | The model explains 95 % of the variation in ethanol content (1.0 = perfect) |
| RMSEP | ±0.70 % | Typical error on those 36 unseen samples |
| RPD | 4.6 | A quality score. Above 3 is considered good enough for screening |

- **Predicted vs lab value chart:** each dot is a sample. If the model were perfect, all dots would
  sit on the diagonal line. They sit close to it.
- **"What the model looks at" chart (VIP):** which parts of the spectrum the model relies on most.
  The tall peaks match ethanol's known vibration bands, so the model is using real chemistry, not
  noise.

### Two honest warning boxes

- **"Water doesn't work, and that's expected."** The water model scores R² 0.27, no better than
  guessing water from the ethanol value alone. Reason: water's signal is outside this instrument's
  range, and these samples contain very little water anyway. **For water, use NIR or a Karl Fischer
  lab test.**
- **"Recalibrate before use."** These are European E0–E10 petrols, and in them ethanol tends to
  appear with another additive (ETBE). Indian E20 is different, so the model must be re-trained on
  Indian E20 samples before real use.

**Say it like this:** "A ten-second laser scan of each tanker gives us the ethanol content to within
about one percentage point, with an error bar, and an automatic pass, review or fail. We tested it
on real fuel samples it had never seen. It does *not* measure water well with this instrument, and
we say so; for water you need NIR or a lab test."

---

## Chapter 5 · Playground: "Try to break it"

**What you see:** The real trained model running live in your browser on real unseen samples, with
sliders to damage the spectrum.

**Controls:**
- **Test sample:** pick any of the held-out real samples.
- **Noise:** adds random fuzz, like a bad or rushed measurement.
- **Baseline tilt:** adds a slope, like stray light or fluorescence.
- **Shift:** moves the spectrum sideways, like a badly calibrated instrument.
- **Declared grade (E10 / E20):** what the tanker paperwork claims the fuel is.

**What to show:**
1. With no damage, the prediction is close to the lab value and the verdict is sensible.
2. Add lots of noise, tilt or shift: the prediction drifts away from the lab value. Watch whether the
   error bar crosses the limit (verdict becomes REVIEW) or the sample is flagged as unlike the
   training data. Try this before presenting so you know which settings show it best.
3. Switch to **declared E20**: these samples are really E0–E10, so the check should FAIL them,
   which is exactly what a depot needs to catch mislabelled loads.

**Say it like this:** "This is the actual model, not a recording. If I damage the measurement, the
system becomes less certain and asks for a lab check instead of giving a confident wrong answer. If
I claim an E10 sample is E20, it fails, as it should."

---

## Chapter 6 · Layer B: "Watch every tank"

**What you see:** A live simulation of one petrol-pump tank during the 2024 monsoon (26 June – 9 July),
driven by real Varanasi weather. You can change conditions and the simulation and forecast re-run
instantly.

**Main chart:** margin to separation over time.
- **Blue line:** the simulated "true" margin.
- **Orange dashed line:** the physics-based forecast for the next 72 hours.
- **Green line:** the machine-learning (GBM) forecast (shown for the default settings).
- Smaller charts below: the water layer measured by the tank's gauge (mm) and the rainfall.

**Controls:**
- **Humidity:** make the air wetter or drier.
- **Day–night swing:** bigger temperature swings mean more "breathing".
- **Refill at:** how empty the tank gets before a delivery (an emptier tank has more air space).
- **Fill-cap seal:** sealed / minor leak / major leak.
- **Weekly drain-out:** "Solution 4": once a week, pump out any water from the tank bottom.
- **Play / scrub:** replay the two weeks.

**Tiles:**
- **Forecast time to separation:** e.g. "30 h" or "> 72 h".
- **Alert:**
  - **SAFE:** nothing expected
  - **WATCH:** the margin is forecast to drop below 25 % within 72 h, so check the tank
  - **ACT:** separation (margin ≤ 0) is forecast within 48 h, so act now (drain, stop sales, inspect)
- **First separation:** when the tank first split, and how much rain water has entered.

**What to demonstrate:**
1. Set the seal to **sealed**: breathing alone never causes separation.
2. Set a **major leak**: the margin falls after storms, and the alert goes WATCH, then ACT, *before*
   the line hits zero.
3. Turn on **weekly drain-out**: separation is delayed or prevented.

**Two forecasting methods:**
- **Physics roll-forward:** estimates how fast water is entering from recent gauge readings, then
  projects forward using the weather forecast (cold nights lower the limit) and expected deliveries.
  Simple, explainable.
- **GBM (gradient-boosted trees, XGBoost):** a machine-learning model trained on two years of
  simulated tanks. It learns patterns from sensor history and weather features.

**Say it like this:** "This is a digital twin of one tank in last year's monsoon. With a good seal
nothing happens. With a leaking cap, rain gets in, and the system raises a warning about a day and a
half before the fuel splits. Turning on a weekly drain-out keeps it safe."

**If someone asks:** *"Are these real petrol pumps?"* No. No public data from Indian tank gauges with
water readings exists. The tank is simulated with real physics and real weather; the leak sizes are
assumptions.

---

## Chapter 7 · The system: "How it fits together"

**What you see:** A flow diagram.

- **Inputs (left):** tanker sample spectrum; tank gauge readings every 30 minutes (fuel level, bottom
  water layer, temperature); weather and forecast; drain-out records.
- **Models (middle):** Layer A (PLS: ethanol and water ± error) and Layer B (forecasts the margin to
  separation 72 h ahead). A dotted arrow shows that Layer A's measurement of water at delivery feeds
  into Layer B.
- **Outputs (right):** depot decision (release / re-test / reject before dispatch) and tank alert
  (SAFE / WATCH / ACT, per tank, 24–48 h ahead).

**Why drain-out records matter:** every time a station drains water out and records how much, that
becomes real labelled data that can be used to check and improve Layer B. That is how the system
would learn from the field.

**Say it like this:** "The depot check decides whether a tanker's load goes out. The tank monitor
uses sensors and weather to warn each pump. Drain-out records close the loop and give us real data
to improve the forecast."

---

## Chapter 8 · Results & limits: "What we can claim"

**What you see:** Two cards ("Validated" and "Not yet validated"), a model-comparison chart, three
headline findings, and a call for data.

### Validated (REAL DATA)
- Ethanol from a handheld Raman scan: **±0.92 %** (repeated cross-checking) and ±0.70 % on the
  held-out test.
- Ethanol at E20 by a second instrument type (FTIR) on lab blends: unseen E20 samples predicted at
  **20.8 %**.
- The water-tolerance curve is within **15 %** of 21 measurements (E5–E30), erring on the safe side.

### Not yet validated
- Commercial Indian E20: the Raman model has only seen 0–10 % ethanol, and the FTIR test used lab
  substitutes for petrol.
- Water by Raman: fails, for the physical reason explained above.
- **Every** Layer B number comes from simulated tanks.

### Forecast model comparison (80 simulated test tanks, 20 separation events, trained on 2022–23 weather, tested on 2024)

| Model | Separations caught early | Alerts that were right | Typical warning time |
|---|---|---|---|
| Original project's model | 0 of 20 | – | – |
| GBM (our improved ML model) | 16 of 20 | 69 % | ~42 h |
| Physics roll-forward | 8 of 20 | 51 % | ~46 h |

The original model in the repo could not catch any separation in advance; the rebuilt models can.

### Three headline findings (simulation)
1. **0 of 97** sealed tanks separated from breathing alone, which agrees with the US EPA.
   **Message: fix the seals, and humid air is not the issue.**
2. **69 → 13 of 70** tanks with a major leak separate without vs with **weekly drain-outs**.
   **Message: a simple weekly drain routine (Solution 4) prevents most incidents.** (How big the
   effect is depends on an assumed rate.)
3. **Volume reconciliation** (comparing the gauge reading with the sales book) spotted **all 20**
   separations within about 1.5 hours. This is *detection after the fact*, not a forecast, but it is a
   cheap safety net.

**The call for data:** to validate Layer B for real, we need oil-company tank-gauge logs, delivery
records and drain-out volumes from real tanks through one monsoon.

**Say it like this:** "What's proven on real data: the ethanol check works, including at 20 %, and our
water-tolerance curve matches published measurements. What is still a simulation: everything about
the tanks. Even so, the simulation gives two clear practical messages: seals matter far more than
humidity, and weekly drain-outs prevent most separations."

---

## Chapter 9 · Validation: "How we checked it"

This chapter answers: *"How do we know these numbers are not luck or self-deception?"* We tested
each claim in several different ways, on every relevant public dataset we could find.

### The three top numbers
- **±0.92 %:** ethanol error when we repeat the whole build-and-test process 10 times on different
  random splits of all the Raman samples. More trustworthy than a single test.
- **20.8 %:** what a second instrument type (FTIR) predicted for 22 real E20 lab blends that were
  completely hidden from training. The true value was 20 %.
- **5 %:** how far our water-tolerance curve is from the official US EPA/API E10 measurement curve.

### Chart: water tolerance, our curve vs measurements
33 measured points from three independent studies (Johansen & Schramm 2009, US EPA 1995, Haq & Ali
1990), compared with our curve. Near E20 our curve is slightly *lower* than measured, so the alarm
would sound a little early, which is the safe direction. We also tried fitting our own new curve to
these points; it did *worse* when tested fairly, so we kept the published one.

### Chart: ethanol by FTIR, 0–90 % blends
210 real lab-made spectra (public dataset on Zenodo). Dots close to the diagonal = accurate.
R² 0.98 overall; about ±1.6 % in the E15–E25 range that matters for E20. Caveat: these blends use
pure chemicals that imitate petrol (heptane, isooctane, toluene…), not pump fuel.

### Chart: Layer B on other cities and wrong assumptions
We trained the forecasters **only on Varanasi**, then tested them on **Delhi, Mumbai, Chennai,
Kolkata and Guwahati** (real 2024 weather), and on fleets where we deliberately changed the hidden
physics (leaks twice as big or small, water dissolving faster or slower, noisier sensors, a 15 %
higher tolerance). This checks whether the models still work when the world doesn't match our
assumptions.

Two scores per model, with 95 % confidence ranges:
- **Recall:** what fraction of separations got an early ACT alert.
- **Precision:** what fraction of ACT alerts were followed by a real separation (i.e. not false alarms).

| Model (median of six cities) | Separations caught | Alerts that were right |
|---|---|---|
| GBM (machine learning) | 83 % | 46 % |
| Physics roll-forward | 64 % | 69 % |
| Ensemble: ACT only when both agree | 40 % | 90 % |

**The key lesson:** the ML model catches the most, but in climates wetter than it was trained on it
raises too many false alarms (in Mumbai only 7 % of its alerts were right). The physics model is more
reliable. **Recommendation: use the physics model, or "both must agree", for ACT alerts (which cost
money: stopping sales, draining), and use the ML model for early WATCH alerts (which are cheap: just
check the tank).**

### The expandable panels
- **All 12 fuel properties from the same Raman spectra:** the same scans also predict other fuel
  properties well (ETBE, MTBE, benzene, octane number, aromatics). One scan, many checks.
- **Model comparison:** PLS vs ridge, SVR, random forest and gradient boosting. They all land at
  ±0.68–0.70 except gradient boosting (worse), so the simple, explainable PLS is the right choice.
- **Chance test (y-randomisation):** we shuffled the ethanol labels 200 times and retrained. The
  shuffled models had errors around 3.2, versus our 0.70, so the result is not luck (p = 0.005).
- **Learning curve:** the error keeps falling as samples are added, so more Indian samples would
  improve the model further.
- **Error by grade:** ±0.5 at E0, ±1.0 at E5 and E10. The error grows with ethanol, so expect a
  bit more at E20.
- **Error-bar honesty:** our 95 % error bars actually contained the true value 94 % of the time.
- **FTIR: whole fuel families held out:** we removed an entire family of blends at a time and
  predicted it. Errors range from 1.3 to 3.6 %, and 6.3 % for the toluene-only family (very unlike the
  rest), showing the model needs training data similar to the real fuel.

**Say it like this:** "We didn't just test once. We repeated the test ten times, checked that a
model trained on shuffled labels fails, tested on a second instrument type at exactly 20 % ethanol,
compared our water curve with 33 published measurements, and tested the tank forecast in five other
cities and under deliberately wrong assumptions. That last test changed our recommendation."

---

## Chapter 10 · Sources & assumptions

**What you see:** A filterable table of every constant used (52 entries), each with its source or the
label ASSUMPTION (22 are assumptions), a reference list, and instructions to reproduce everything.

**What it means:** Nothing is hidden. Every number lives in one file (`config/constants.yaml`). Anyone
can filter for "ASSUMPTION" to see exactly what still needs to be verified with real data (mostly tank
properties: leak sizes, sensor noise, how fast settled water dissolves).

**Say it like this:** "Every number has a citation or is honestly marked as an assumption, and
anyone can rerun the whole thing with one command."

---

## Glossary (one line each)

| Term | Plain meaning |
|---|---|
| E10 / E20 | Petrol with 10 % / 20 % ethanol by volume |
| Phase separation | Fuel splitting into a petrol layer and a heavy ethanol–water bottom layer |
| Water tolerance | Maximum water the fuel can hold before it separates; drops as temperature drops |
| Margin to separation | How much more water the tank can take, as a %; 0 % = separation |
| wt % / % v/v / mg/kg | Percent by weight / percent by volume / milligrams per kilogram (ppm by weight) |
| Spectrum / spectroscopy | A "light fingerprint" of the molecules in a sample |
| Raman / NIR / FTIR | Three types of light-fingerprint instrument |
| PLS | The standard statistical method that turns a spectrum into a number |
| Latent variables | The few summary scores PLS compresses a spectrum into |
| R² | How much of the variation the model explains (1 = perfect, 0 = useless) |
| RMSEP | Typical prediction error on unseen samples, in the same units as the answer |
| RPD | Quality score; above 3 = good enough for screening |
| Cross-validation | Repeatedly hiding part of the data, training on the rest, and testing on the hidden part |
| Nested CV | Cross-validation where even the model-choosing step is redone inside each split, so there is no cheating |
| Held-out test set | Samples locked away and used only once, at the very end |
| Bootstrap / 95 % CI | Resampling the results many times to get a range the true value likely falls in |
| Permutation test | Shuffling the answers to prove the model isn't just finding patterns by chance |
| GBM / XGBoost | A machine-learning method built from many small decision trees |
| Physics roll-forward | Forecasting by projecting the measured water-entry rate forward with physics |
| Ensemble | Combining models; here, ACT only when both models agree |
| Recall | Share of real incidents that got an alert in time |
| Precision | Share of alerts that were real (not false alarms) |
| Lead time | How many hours before the incident the alert came |
| Change-point detection | Spotting the moment a sensor reading suddenly shifts |
| Volume reconciliation | Comparing gauge volume with the sales book to spot unexplained changes |
| Drain-out (Solution 4) | Regularly pumping water off the tank bottom |
| ERA5 | Europe's high-quality archive of historical global weather |
| Digital twin | A simulation that mirrors a real system so you can experiment safely |

---

## One-minute summary for the panel

> "E20 fuel can hold under 2 % water before it splits into layers, and colder weather lowers that
> limit. We built a two-layer early-warning system. At the depot, a ten-second handheld spectrum of
> each tanker gives the ethanol content to within about one percentage point, tested on real fuel
> samples, with an automatic pass, review or fail; on a second instrument type it correctly read
> unseen E20 blends as 20.8 %. At each petrol pump, a forecast using the tank gauge and the weather
> warns about a day and a half before separation. That part is validated on simulated tanks under
> real weather from six Indian cities, because no public tank data exists. The simulation also shows
> that fixing seals and weekly drain-outs prevent most incidents. Everything is labelled real,
> literature or simulated, and all assumptions are listed."

---

## What NOT to claim (to stay honest under questioning)

- ❌ "Layer B is proven on real petrol pumps." It is a simulation with real weather.
- ❌ "The Raman model measures water." It doesn't; water needs NIR or Karl Fischer.
- ❌ "The model is ready for Indian E20." It must be recalibrated on Indian E20 samples first.
- ❌ "We used NIR data." The public data is Raman; FTIR was used as a second check.
- ❌ "0.5 % is the E20 water limit." That limit is for neat ethanol; E20's quality limit is 0.05 % v/v.
- ✅ Safe phrasing: "validated on real fuel spectra for ethanol; demonstrated in simulation for tanks;
  here is exactly the data we need to validate it in the field."
