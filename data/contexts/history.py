"""A labelled history: what an agent writes to the memory over two months, each entry tagged with
the context it belongs to at the time it was written. Sessions are a list each; a context may
stop in one session and go on in a later one, and several contexts may pass in one session."""

SESSIONS = [
    ("2026-09-01 09:10", [
        ("job", "Alex started a new job at Brightwork in September 2026 as a data engineer."),
        ("job", "Alex's manager at Brightwork is Rachel."),
        ("job", "Alex's team at Brightwork owns the billing data pipelines."),
        ("job", "Priya is on Alex's team at Brightwork and sits next to Alex."),
        ("cats", "Alex has two cats, Miso and Tofu."),
        ("cats", "Tofu, Alex's cat, sheds much more than Miso."),
        ("cats", "Miso, Alex's cat, is due for her vaccination in October 2026."),
    ]),
    ("2026-09-03 20:40", [
        ("flat", "Alex lives with Tom in a 70 square metre flat in Berlin."),
        ("flat", "The flat's living room has a thick shaggy rug."),
        ("flat", "The doorways of Alex's flat have 2 cm thresholds."),
        ("flat", "The landlord of Alex's flat is Mr. Keller."),
        ("flat", "Mr. Keller promised to fix the bathroom window in Alex's flat by mid-September 2026."),
    ]),
    ("2026-09-05 12:15", [
        ("trip", "Alex and Tom plan a trip to Lisbon in November 2026."),
        ("trip", "Alex wants the Lisbon trip to include a day in Sintra."),
        ("trip", "Tom does not like early flights."),
        ("job", "Rachel asked Alex to present the billing pipeline redesign at the October 2026 all-hands."),
        ("job", "Alex's billing pipeline redesign moves the jobs from cron to Airflow."),
    ]),
    ("2026-09-09 18:30", [
        ("health", "Alex has a dust allergy that flared up in September 2026."),
        ("health", "Alex's doctor, Dr. Weiss, told Alex to keep the floors and the air as clean as possible."),
        ("health", "Dr. Weiss prescribed Alex an antihistamine, cetirizine, once a day."),
        ("vacuum", "Alex's old Roomba robot vacuum died in September 2026 after six years."),
        ("vacuum", "Alex wants a new robot vacuum under 400 euros."),
        ("vacuum", "Alex does not want a robot vacuum that works only through a cloud account."),
        ("vacuum", "The new robot vacuum has to be quiet because Tom takes calls at home in the mornings."),
    ]),
    ("2026-09-10 08:05", [
        ("vacuum", "Alex is considering the Roborock Q7 Max and the Dreame D10 Plus as robot vacuums."),
        ("vacuum", "Alex read that the Dreame D10 Plus climbs thresholds up to 2 cm."),
        ("vacuum", "Alex ordered the Dreame D10 Plus robot vacuum for 329 euros on 2026-09-10."),
    ]),
    ("2026-09-14 19:00", [
        ("flat", "Mr. Keller has not fixed the bathroom window in Alex's flat, as of 2026-09-14."),
        ("flat", "Alex wrote to Mr. Keller again about the bathroom window on 2026-09-14."),
        ("cats", "Tofu, Alex's cat, stopped eating on 2026-09-13."),
        ("cats", "Alex took Tofu to the vet, Dr. Brandt, on 2026-09-14."),
        ("cats", "Dr. Brandt found that Tofu had a mild stomach infection and prescribed a special diet."),
    ]),
    ("2026-09-18 21:20", [
        ("mila", "Alex's sister Mila lives in Belgrade."),
        ("mila", "Mila is getting married to Stefan on 2027-06-12 in Belgrade."),
        ("mila", "Mila asked Alex to be a witness at her wedding."),
        ("mila", "Mila would love a candlelight concert as part of her hen party."),
        ("trip", "Alex and Tom booked flights to Lisbon for 2026-11-12 to 2026-11-17."),
        ("trip", "The Lisbon flights leave Berlin at 11:40, late enough for Tom."),
    ]),
    ("2026-09-24 10:30", [
        ("job", "Rachel left Brightwork on 2026-09-23."),
        ("job", "Tom Becker is Alex's new manager at Brightwork from 2026-09-24."),
        ("job", "Tom Becker moved the all-hands presentation of the billing redesign to November 2026."),
        ("job", "Marco from sales at Brightwork asked Alex for a revenue dashboard."),
    ]),
    ("2026-09-30 17:45", [
        ("running", "Alex started running three times a week in late September 2026."),
        ("running", "Alex runs along the Landwehr canal in Berlin."),
        ("running", "Alex wants to run the Berlin half marathon in April 2027."),
        ("running", "Alex's knee hurt after a 10 km run on 2026-09-29."),
        ("health", "Dr. Weiss said Alex's knee pain is a mild strain and to rest for a week."),
        ("health", "Alex's dust allergy is better since the new robot vacuum arrived."),
    ]),
    ("2026-10-06 13:00", [
        ("vacuum", "The Dreame D10 Plus robot vacuum gets stuck on the shaggy rug in Alex's living room."),
        ("vacuum", "Alex set a no-go zone around the living room rug for the Dreame D10 Plus."),
        ("cats", "Miso, Alex's cat, got her vaccination on 2026-10-05 at Dr. Brandt's."),
        ("cats", "Tofu, Alex's cat, is eating normally again on the special diet."),
        ("flat", "Mr. Keller fixed the bathroom window in Alex's flat on 2026-10-04."),
        ("flat", "Mr. Keller announced a rent increase of 60 euros from January 2027."),
    ]),
    ("2026-10-12 20:10", [
        ("mila", "Mila and Stefan chose the Hotel Moskva in Belgrade for their wedding reception."),
        ("mila", "Mila asked Alex to give a speech at the wedding."),
        ("mila", "Alex wants to find a candlelight concert in Belgrade for Mila's hen party in May 2027."),
        ("trip", "Alex and Tom booked a guesthouse in Alfama, Lisbon, for the November 2026 trip."),
        ("trip", "Alex reserved a day trip to Sintra on 2026-11-14."),
    ]),
    ("2026-10-19 09:30", [
        ("job", "Alex finished the Airflow migration of the billing pipelines on 2026-10-17."),
        ("job", "Tom Becker asked Alex to mentor a new junior engineer, Lena, at Brightwork."),
        ("job", "Lena joins Alex's team at Brightwork on 2026-11-02."),
        ("running", "Alex is back to running after the knee strain, as of 2026-10-18."),
        ("running", "Alex ran 12 km along the Landwehr canal on 2026-10-18 without knee pain."),
    ]),
]
