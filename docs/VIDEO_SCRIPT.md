# Video walkthrough script (blog scroll-through, target ~4:40, hard limit 5:00)

Scroll http://localhost:3000 top to bottom. **[Show]** = screen.
Everything else = what you say. Talk it like a class presentation. ~680 words.

---

**0:00 intro** [Show: title + first paragraph]

hey, i'm Nikhil. this project is called SoldierPhysio, and the question is pretty simple:
can today's best AI models keep a soldier from getting heat stroke?

this is a real problem. in 2024 the Army had about 36 heat strokes and 184 heat
exhaustion cases per 100,000 soldiers, and it's been going up every year since 2020. and
people are starting to pitch AI as a helper for these calls.

**0:20 the setup** [Show: second paragraph]

so picture a medic watching soldiers exercise in the heat. they can see heart rate, skin
temperature, how hard the soldier is working, and the weather. what they can't see is
core body temperature, which is the number that actually tells you if someone is about to
get heat stroke. so the medic keeps making one call: let this person keep going, or pull
them out.

the medic also has the Army's heat chart. it's basically a cheat sheet that says how long
soldiers can work and how much water they need, depending on how hot it is outside and
how hard the work is.

i gave 14 AI models the same 21 cases. the data comes from a real study where people
biked in a heat chamber and their core temperature was actually measured. so for every
case, i know the right answer. the rule is: if their core will hit 38.5 Celsius, about
101 Fahrenheit, in the next 15 minutes, you pull them.

**1:00 leaderboard** [Show: leaderboard → score vs cost chart]

the best model scored 54.5 out of 100. i only ran each case once, so a few points between
models is mostly noise. and look at this chart: price doesn't really line up with score.
i'll come back to that.

**1:15 finding 1: old rulebook** [Show: finding 1 + bar chart]

first finding. the Army updated its heat chart in 2022. for the situation i asked about,
a medium-hot day with medium work, the new chart says there's no time limit. the old 2003
chart said 40 minutes of work, 20 minutes of rest. even though i told the models to use the
2022 version, 18 out of 28 answers gave the old 40/20. only 3 got it right.

my guess for why: the old chart was around for almost 20 years, so it's all over the
internet, in training slides, websites, all of it. the update is newer and way less
written about. so the models just repeat what they've seen the most, and they say it super
confidently.

**1:55 finding 2: pulling everyone** [Show: finding 2 + stacked bars]

second, on keep or pull, the models were right 55 percent of the time. that's basically a
coin flip. and the mistakes mostly go one way: out of the soldiers who were actually safe,
they pulled 53 out of 84.

i think this is because these models are trained to be extra careful about anything
medical. "pull them, just to be safe" sounds responsible. but in real life pulling isn't
free. you lose training time, and if a tool keeps raising false alarms, people stop
listening to it.

**2:35 finding 3: steady work** [Show: finding 3]

third. there's a known trap called thermal lag. a soldier slows down, but their core keeps
heating up for a while, kind of like a car engine staying hot after you turn it off. the
models were actually good at this, 34 out of 42. probably because it's a textbook idea
they've read a lot about.

where they missed was the boring cases. a soldier working at the same pace, heart rate not
doing anything dramatic, while their core slowly climbs past the limit. 13 of those got
missed. there's nothing in the data that screams danger, so they let it go. and their
temperature guesses were usually off by 0.2 to 0.4 degrees, which is enough to flip the
call.

**3:10 finding 4: overriding** [Show: finding 4]

fourth. i gave the models a matched pair. in one, the sensors look calm but the soldier is
actually overheating, so you should break the chart's rules and pull them. in the other,
the sensors look scary but the soldier is fine, so you should follow the chart. almost
every model chose to break the rules on both. only one model, Grok, told them apart.

so they're not really reading the numbers. the question is about heat, heat sounds
dangerous, so they react to that.

**3:40 finding 5: coding is easy** [Show: finding 5]

fifth, the one thing they're good at. i gave them a coding task: build a tool that guesses
core temperature better than the Army's existing method. 76 out of 98 beat it. coding and
fitting data is what these models are trained on the most, so this makes sense.

**3:55 finding 6: cost** [Show: finding 6 + cost bars]

and sixth, money doesn't help. running everything cost 29 cents on the cheapest model and
almost 30 dollars on the most expensive. one model that cost about a dollar beat the 30
dollar one. that tracks, because the problem isn't thinking harder. it's having the
current rules and good judgment.

**4:15 how it's graded** [Show: Methodology → scoring table]

quick note on grading. anything with a right answer is checked by code against the real
measured temperature or the actual 2022 chart. i also had a separate AI grade the
reasoning, but every finding i just showed comes from the code grading only.

**4:30 wrap up** [Show: scroll to bottom / repo link]

so overall, the models can code and they know the textbook stuff. what they're missing is
what a real medic has: the current rules, and the judgment to leave a hot but healthy
soldier alone. everything is public, and you can re-score the whole thing yourself for
free. thanks for watching.

**~4:45 end**

---

Tips
- zoom browser to ~125% so the charts are readable
- running long? cut the cost chart line at 1:00 first, then finding 6
- the "why" parts are your guesses, and the script says so ("my guess", "i think", "probably")
- after upload: set "anyone with the link", test in incognito, swap `TODO_VIDEO_LINK` on README line 5
