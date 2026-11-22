"""Eval scenarios: onboarding answers, chat steps and the expected values after each step.

Every expected date is computed by hand from the documents, not from the engine:
- week = 7 calendar days (KP art. 183¹ § 1), periods inclusive, the day of birth is day 1 after
  the birth (CLAUDE.md, open question on day counting);
- maternity leave 20/31/33 weeks for 1/2/3 children (KP art. 180 § 1); at most 6 weeks before
  the due date (KP art. 180 § 2, guide p. 5); weeks before the birth count towards it (§ 3);
  without leave before the birth it starts on the day of birth (KP art. 183¹ § 2);
- 14 weeks after the birth used by the mother personally (guide p. 5);
- parental leave 41/43 weeks, 65/67 with "Za życiem", 9 weeks exclusive for each parent
  (KP art. 182¹ᵃ § 1, 2, 4; guide p. 7), so the mother's share is 32/34/56/58 weeks; until
  31 December of the year the child turns 6 (KP art. 182¹ᶜ);
- paternity leave 14 days, not longer with twins (guide p. 8), until the child is 12 months
  old: last day = the day before the first birthday (CLAUDE.md open question);
- supplementary leave: a week for every started week in hospital within 8 weeks after a birth
  between the 28th and 37th week (KP art. 180² § 1 pkt 2, § 3);
- stillbirth / death before 8 weeks: 8 weeks after the birth, not less than 7 days from the
  death (KP art. 180¹ § 1, guide p. 6; 7 days counted from the next day: open question);
- the father takes over after 14 weeks (guide p. 7, KP art. 180 § 4-5), after 8 weeks when the
  mother is in hospital (KP art. 180 § 10-11), after the mother's death from the next day
  (KP art. 180 § 12).

The dates assume the server's "today" is 2026-11-21 (due dates must be in the future, birth
dates in the past). Shift every date by the same number of days to run it later.

Step fields:
  say / event        the user's message, or the app event "timeline_ready"
  patch              scenario fields the app changes before the message, without the chat
                     (PATCH /api/session/{id}/scenario: the week tiles, the 81,5% switch)
  no_setters         the turn must not record anything (no set_* tool call)
  tools              tool calls that must happen, with a subset of their arguments
  no_tools           tools that must NOT be called (e.g. a hypothetical question)
  timeline           expected timeline after the step (see checks.check_timeline)
  changed            element ids that must be highlighted as changed
  changed_notes      explanation points that must be marked as changed
  mention            {"dates": [...], "numbers": [...]} the reply must state
  require / forbid   regexes the reply must / must not match
  not_repeat         dates of unchanged elements the reply should not repeat (soft)
  question           key of the next interview question after the step (None = finished)
  sensitive          no "!", words of sympathy, no congratulations
  out_of_scope       the reply says the app does not cover it yet
"""

MOTHER_EXPECTED = {
    "role": "mother",
    "child_born": False,
    "date": "2027-03-15",
    "children_count": 1,
    "work": "employment",
    "earnings": "5k-8k",
}

BASE_2027_03_15 = {
    "segments": {
        "prenatal-window": ["2027-02-01", "2027-03-14"],  # 6 weeks before the due date
        "maternity": ["2027-03-15", "2027-08-01"],  # 20 weeks from the due date
        "parental": ["2027-08-02", "2028-03-12"],  # 41 - 9 = 32 weeks
        "paternity": ["2027-03-15", "2027-03-28"],  # 14 days
        "parental-father": ["2028-03-13", "2028-05-14"],  # 9 weeks
    },
    "markers": {
        "due-date": "2027-03-15",
        "personal-weeks": "2027-06-20",  # 14 weeks after the birth
        "paternity-deadline": "2028-03-14",
        "parental-deadline": "2033-12-31",
    },
}

CITES_180_1 = r"180\s*§\s*1\b"

SCENARIOS = [
    {
        "id": "twins-and-back",
        "about": "one child -> twins -> one child (KP art. 180 § 1, art. 182¹ᵃ § 1)",
        "runs": 3,
        "onboarding": MOTHER_EXPECTED,
        "steps": [
            {
                "event": "timeline_ready",
                "timeline": BASE_2027_03_15,
                "mention": {"dates": ["2027-08-01"], "numbers": [20]},
                "question": "leave-before-birth",
            },
            {
                "say": "Właśnie dowiedzieliśmy się, że będą bliźnięta.",
                "tools": [{"name": "set_children_count", "args": {"count": 2}}],
                "timeline": {
                    "segments": {
                        "maternity": ["2027-03-15", "2027-10-17"],  # 31 weeks
                        "parental": ["2027-10-18", "2028-06-11"],  # 43 - 9 = 34 weeks
                        "parental-father": ["2028-06-12", "2028-08-13"],
                        "paternity": ["2027-03-15", "2027-03-28"],  # twins: no longer (p. 8)
                    },
                    "markers": {"personal-weeks": "2027-06-20", "paternity-deadline": "2028-03-14"},
                    "notes": ["more-children"],
                },
                "changed": ["maternity", "parental", "parental-father"],
                "changed_notes": ["more-children", "parental", "computed"],
                "mention": {"dates": ["2027-10-17"], "numbers": [31]},
                "require": [CITES_180_1],
                "forbid": [r"\b40 tyg"],
                "not_repeat": ["2028-03-14", "2027-02-01"],
                "question": "leave-before-birth",
            },
            {
                "say": "Przepraszam, pomyliłam się — jednak będzie jedno dziecko.",
                "tools": [{"name": "set_children_count", "args": {"count": 1}}],
                "timeline": {
                    "segments": {
                        "maternity": ["2027-03-15", "2027-08-01"],
                        "parental": ["2027-08-02", "2028-03-12"],
                        "parental-father": ["2028-03-13", "2028-05-14"],
                    },
                    "no_notes": ["more-children"],
                },
                "changed": ["maternity", "parental"],
                "changed_notes": ["parental", "computed"],
                "mention": {"dates": ["2027-08-01"], "numbers": [20]},
                "question": "leave-before-birth",
            },
        ],
    },
    {
        "id": "twins-to-triplets",
        "about": "twins -> triplets: 31 -> 33 weeks, parental leave stays 43 (KP art. 180 § 1)",
        "runs": 1,
        "onboarding": {**MOTHER_EXPECTED, "children_count": 2},
        "steps": [
            {
                "event": "timeline_ready",
                "timeline": {
                    "segments": {
                        "maternity": ["2027-03-15", "2027-10-17"],
                        "parental": ["2027-10-18", "2028-06-11"],
                    },
                    "notes": ["more-children"],
                },
                "mention": {"dates": ["2027-10-17"], "numbers": [31]},
                "question": "leave-before-birth",
            },
            {
                "say": "Na ostatnim USG okazało się, że to trojaczki.",
                "tools": [{"name": "set_children_count", "args": {"count": 3}}],
                "timeline": {
                    "segments": {
                        "maternity": ["2027-03-15", "2027-10-31"],  # 33 weeks
                        "parental": ["2027-11-01", "2028-06-25"],  # still 34 weeks
                        "parental-father": ["2028-06-26", "2028-08-27"],
                    }
                },
                "changed": ["maternity", "parental"],
                "changed_notes": ["more-children", "computed"],
                "mention": {"dates": ["2027-10-31"], "numbers": [33]},
                "require": [CITES_180_1],
                "forbid": [r"\b45 tyg"],
                "question": "leave-before-birth",
            },
        ],
    },
    {
        "id": "leave-before-birth",
        "about": "work until the birth -> 6 weeks before -> illegal 8 weeks -> no certificate",
        "runs": 3,
        "onboarding": MOTHER_EXPECTED,
        "steps": [
            {
                "event": "timeline_ready",
                "timeline": BASE_2027_03_15,
                "mention": {"dates": ["2027-02-01"], "numbers": [6]},
                "question": "leave-before-birth",
            },
            {
                "say": "Będę pracować do dnia porodu.",
                "tools": [{"name": "set_leave_before_birth", "args": {"weeks": 0}}],
                "timeline": {
                    "segments": {
                        "work-until-birth": ["2027-02-01", "2027-03-14"],
                        "maternity": ["2027-03-15", "2027-08-01"],  # KP art. 183¹ § 2
                    },
                    "absent": ["prenatal-window", "medical-certificate"],
                },
                "changed": ["work-until-birth"],
                "changed_notes": ["before-birth"],
                "question": "father-work",
            },
            {
                "say": "Zmieniłam zdanie: chcę zacząć urlop macierzyński 6 tygodni przed porodem.",
                "tools": [{"name": "set_leave_before_birth", "args": {"weeks": 6}}],
                "timeline": {
                    "segments": {
                        "maternity-prenatal": ["2027-02-01", "2027-03-14"],
                        "maternity": ["2027-03-15", "2027-06-20"],  # 20 - 6 = 14 weeks left
                        "parental": ["2027-06-21", "2028-01-30"],
                        "parental-father": ["2028-01-31", "2028-04-02"],
                    },
                    "documents": {"medical-certificate": ["2027-02-01", False]},
                    "absent": ["work-until-birth"],
                    # nothing is left after 14 weeks for the father to take over
                    "no_notes": ["takeover"],
                },
                "changed": ["maternity-prenatal", "maternity", "parental", "medical-certificate"],
                "changed_notes": ["before-birth", "computed"],
                "mention": {"dates": ["2027-02-01", "2027-06-20"], "numbers": [6]},
                "require": [r"zaświadczeni"],
                "question": "certificate",
            },
            {
                "say": "A gdybym jednak zaczęła urlop 8 tygodni przed porodem?",
                "timeline": {
                    "segments": {"maternity-prenatal": ["2027-02-01", "2027-03-14"]},
                },
                "mention": {"numbers": [6]},
                "require": [r"180\s*§\s*2|s\.\s*5\b"],
                "question": "certificate",
            },
            {
                "say": "Nie mam jeszcze zaświadczenia lekarskiego.",
                "tools": [{"name": "set_medical_certificate", "args": {"has_certificate": False}}],
                "timeline": {"documents": {"medical-certificate": ["2027-02-01", False]}},
                "mention": {"dates": ["2027-02-01"]},
                "question": "father-work",
            },
        ],
    },
    {
        "id": "contract-insurance",
        "about": "contract of mandate: not registered -> no benefit -> registered (p. 3, 5, 10)",
        "runs": 3,
        "onboarding": {**MOTHER_EXPECTED, "work": "contract", "earnings": "under-5k"},
        "steps": [
            {
                "event": "timeline_ready",
                "timeline": {"segments": {"maternity": ["2027-03-15", "2027-08-01"]}},
                "question": "mother-insurance",
            },
            {
                "say": "Nie, nie jestem zgłoszona do dobrowolnego ubezpieczenia chorobowego.",
                "tools": [{"name": "set_voluntary_insurance", "args": {"registered": False}}],
                "timeline": {
                    "segments": {
                        "paternity": ["2027-03-15", "2027-03-28"],
                        # mother uninsured: parental benefit for the father (p. 7), 41 - 9
                        "parental-father": ["2027-03-29", "2027-11-07"],
                    },
                    "absent": ["maternity", "parental", "prenatal-window", "personal-weeks"],
                },
                "changed": ["parental-father"],
                "changed_notes": ["insurance"],
                "require": [
                    r"nie (będzie )?(Ci |ci )?(przysługiwa|przysługuje)|nie masz\b.{0,20}prawa|"
                    r"nie ma\b.{0,20}prawa|nie dostaniesz|nie nabędziesz|nie nabywasz"
                ],
                "forbid": [r"\b20 tyg"],
                "question": "father-work",
            },
            {
                "say": "Pomyliłam się: jednak jestem zgłoszona i opłacam składkę chorobową.",
                "tools": [{"name": "set_voluntary_insurance", "args": {"registered": True}}],
                "timeline": {
                    "segments": {
                        "maternity": ["2027-03-15", "2027-08-01"],
                        "parental": ["2027-08-02", "2028-03-12"],
                        "parental-father": ["2028-03-13", "2028-05-14"],
                    }
                },
                "changed": ["maternity", "parental", "parental-father"],
                "changed_notes": ["insurance"],
                "question": "leave-before-birth",
            },
        ],
    },
    {
        "id": "born-early-on-leave",
        "about": "on leave 4 weeks before the due date, the child comes 3 weeks early",
        "runs": 1,
        "onboarding": {**MOTHER_EXPECTED, "date": "2026-12-12"},
        "steps": [
            {
                "event": "timeline_ready",
                "timeline": {
                    "segments": {
                        "prenatal-window": ["2026-10-31", "2026-12-11"],
                        "maternity": ["2026-12-12", "2027-04-30"],
                    }
                },
                "question": "leave-before-birth",
            },
            {
                "say": "Od 14 listopada jestem już na urlopie macierzyńskim, czyli 4 tygodnie "
                "przed terminem porodu.",
                "tools": [{"name": "set_leave_before_birth", "args": {"weeks": 4}}],
                "timeline": {
                    "segments": {
                        "maternity-prenatal": ["2026-11-14", "2026-12-11"],
                        "maternity": ["2026-12-12", "2027-04-02"],  # 20 weeks from 14.11
                    },
                    "documents": {"medical-certificate": ["2026-11-14", False]},
                },
                "question": "certificate",
            },
            {
                "say": "Tak, mam zaświadczenie od lekarza.",
                "tools": [{"name": "set_medical_certificate", "args": {"has_certificate": True}}],
                "timeline": {"documents": {"medical-certificate": ["2026-11-14", True]}},
                "question": "father-work",
            },
            {
                "say": "Synek urodził się wczoraj, 20 listopada 2026, wcześniej niż termin.",
                "tools": [{"name": "set_birth_date", "args": {"birth_date": "2026-11-20"}}],
                "timeline": {
                    # She started on 14.11 and gave birth on 20.11: 6 days before the birth.
                    # 20 weeks counted from 14.11 (KP art. 180 § 1 and § 3) end on 02.04.2027.
                    "segments": {
                        "maternity-prenatal": ["2026-11-14", "2026-11-19"],
                        "maternity": ["2026-11-20", "2027-04-02"],
                        "parental": ["2027-04-03", "2027-11-12"],
                    },
                    "markers": {"birth": "2026-11-20", "personal-weeks": "2027-02-25"},
                    "absent": ["medical-certificate", "due-date"],
                },
                "changed": ["maternity"],
                "mention": {"dates": ["2026-11-20"]},
                "question": "hospital",
            },
        ],
    },
    {
        "id": "expected-to-born",
        "about": "works until the birth, then the child is born before the due date",
        "runs": 1,
        "onboarding": {**MOTHER_EXPECTED, "date": "2026-12-12"},
        "steps": [
            {"event": "timeline_ready", "question": "leave-before-birth"},
            {
                "say": "Będę pracować do porodu.",
                "tools": [{"name": "set_leave_before_birth", "args": {"weeks": 0}}],
                "timeline": {"segments": {"maternity": ["2026-12-12", "2027-04-30"]}},
                "question": "father-work",
            },
            {
                "say": "Córka urodziła się wczoraj, 20 listopada 2026.",
                "tools": [{"name": "set_birth_date", "args": {"birth_date": "2026-11-20"}}],
                "timeline": {
                    "segments": {
                        "maternity": ["2026-11-20", "2027-04-08"],
                        "parental": ["2027-04-09", "2027-11-18"],
                        "parental-father": ["2027-11-19", "2028-01-20"],
                    },
                    "markers": {
                        "birth": "2026-11-20",
                        "personal-weeks": "2027-02-25",
                        "paternity-deadline": "2027-11-19",
                        "parental-deadline": "2032-12-31",
                    },
                    "absent": ["due-date", "work-until-birth", "medical-certificate"],
                },
                "changed": ["maternity", "parental", "birth"],
                "changed_notes": ["situation", "computed"],
                "mention": {"dates": ["2027-04-08"]},
                "question": "hospital",
            },
        ],
    },
    {
        "id": "za-zyciem",
        "about": "born child gets the 'Za życiem' certificate: parental 41 -> 65 weeks",
        "runs": 1,
        "onboarding": {**MOTHER_EXPECTED, "child_born": True, "date": "2026-09-01"},
        "steps": [
            {
                "event": "timeline_ready",
                "timeline": {
                    "segments": {
                        "maternity": ["2026-09-01", "2027-01-18"],
                        "parental": ["2027-01-19", "2027-08-30"],
                    }
                },
                "question": "leave-before-birth",
            },
            {
                "say": "Nie byłam na urlopie przed porodem. Dziecko urodziło się o czasie "
                "i nie było w szpitalu.",
                "tools": [
                    {"name": "set_leave_before_birth", "args": {"weeks": 0}},
                    {"name": "set_hospital_care", "args": {"applies": False}},
                ],
                "question": "father-work",
            },
            {
                "say": "Dziecko dostało zaświadczenie „Za życiem”.",
                "tools": [{"name": "set_za_zyciem", "args": {"has_certificate": True}}],
                "timeline": {
                    "segments": {
                        "parental": ["2027-01-19", "2028-02-14"],  # 65 - 9 = 56 weeks
                        "parental-father": ["2028-02-15", "2028-04-17"],
                    },
                    "notes": ["za-zyciem"],
                },
                "changed": ["parental", "parental-father"],
                "changed_notes": ["za-zyciem", "computed"],
                "mention": {"dates": ["2028-02-14"], "numbers": [65, 56]},
                "require": [r"182\s*[¹1]?\s*[ᵃa]\s*§\s*2"],
                "question": "father-work",
            },
        ],
    },
    {
        "id": "premature",
        "about": "born in week 30, 1500 g, 25 days in hospital: 4 weeks of supplementary leave",
        "runs": 1,
        "onboarding": {**MOTHER_EXPECTED, "child_born": True, "date": "2026-10-01"},
        "steps": [
            {
                "event": "timeline_ready",
                "timeline": {
                    "segments": {
                        "maternity": ["2026-10-01", "2027-02-17"],
                        "parental": ["2027-02-18", "2027-09-29"],
                    }
                },
                "question": "leave-before-birth",
            },
            {
                "say": "Nie byłam na urlopie przed porodem.",
                "tools": [{"name": "set_leave_before_birth", "args": {"weeks": 0}}],
                "question": "hospital",
            },
            {
                "say": "Synek urodził się w 30. tygodniu ciąży, ważył 1500 g i był w szpitalu "
                "od 1 do 25 października 2026.",
                "tools": [
                    {
                        "name": "set_hospital_care",
                        "args": {
                            "applies": True,
                            "birth_week": "28-37",
                            "weight_up_to_1000g": False,
                        },
                    }
                ],
                "timeline": {
                    "segments": {
                        "maternity": ["2026-10-01", "2027-02-17"],
                        "supplementary": ["2027-02-18", "2027-03-17"],  # 25 days -> 4 weeks
                        "parental": ["2027-03-18", "2027-10-27"],
                        "parental-father": ["2027-10-28", "2027-12-29"],
                    }
                },
                "changed": ["supplementary", "parental", "parental-father"],
                "changed_notes": ["supplementary", "computed"],
                "mention": {"dates": ["2027-03-17"], "numbers": [4]},
                "require": [r"180\s*[²2]|s\.\s*8\b"],
                "question": "father-work",
            },
        ],
    },
    {
        "id": "father-twins-takeover",
        "about": "father of twins: paternity leave stays 14 days; takeover after 14 weeks",
        "runs": 1,
        "onboarding": {
            "role": "father",
            "child_born": True,
            "date": "2026-09-15",
            "children_count": 2,
            "work": "employment",
            "earnings": "8k-12k",
        },
        "steps": [
            {
                "event": "timeline_ready",
                "timeline": {
                    "segments": {"maternity": ["2026-09-15", "2027-04-19"]},
                    "markers": {"paternity-deadline": "2027-09-14"},
                },
                "question": "mother-work",
            },
            {
                "say": "Mama pracuje na etacie, nie była na urlopie przed porodem, a bliźnięta "
                "urodziły się o czasie i nie były w szpitalu.",
                "tools": [
                    {"name": "set_mother_work", "args": {"work": "employment"}},
                    {"name": "set_leave_before_birth", "args": {"weeks": 0}},
                    {"name": "set_hospital_care", "args": {"applies": False}},
                ],
                "question": None,
            },
            {
                "say": "Przy bliźniętach przysługują mi 4 tygodnie urlopu ojcowskiego, prawda?",
                "no_tools": ["set_children_count", "set_father_takeover"],
                "mention": {"numbers": [14]},
                "require": [r"nie wydłuża|nie wydłużają|nie zmienia|nie jest dłuższ"],
                "question": None,
            },
            {
                "say": "Żona wykorzysta 14 tygodni po porodzie, a dalszą część urlopu "
                "macierzyńskiego przejmę ja.",
                "tools": [{"name": "set_father_takeover", "args": {"takes_over": True}}],
                "timeline": {
                    "segments": {
                        "maternity": ["2026-09-15", "2026-12-21"],
                        "maternity-father": ["2026-12-22", "2027-04-19"],
                    }
                },
                "changed": ["maternity", "maternity-father"],
                "changed_notes": ["takeover", "computed"],
                "mention": {"dates": ["2026-12-22", "2027-04-19"]},
                "question": None,
            },
        ],
    },
    {
        "id": "father-mother-hospital",
        "about": "mother in hospital after 8 weeks: the father uses that part (KP art. 180 § 10)",
        "runs": 1,
        "onboarding": {
            "role": "father",
            "child_born": True,
            "date": "2026-09-01",
            "children_count": 1,
            "work": "employment",
            "earnings": "5k-8k",
        },
        "steps": [
            {"event": "timeline_ready", "question": "mother-work"},
            {
                "say": "Mama pracuje na etacie, nie była na urlopie przed porodem, a dziecko "
                "urodziło się o czasie i nie było w szpitalu.",
                "tools": [
                    {"name": "set_mother_work", "args": {"work": "employment"}},
                    {"name": "set_leave_before_birth", "args": {"weeks": 0}},
                    {"name": "set_hospital_care", "args": {"applies": False}},
                ],
                "question": None,
            },
            {
                "say": "Żona trafiła do szpitala 10 listopada 2026 i wyszła 20 listopada 2026; "
                "przez ten czas nie mogła opiekować się dzieckiem.",
                "tools": [{"name": "set_mother_situation"}],
                "timeline": {
                    "segments": {
                        "maternity": ["2026-09-01", "2026-11-09"],
                        "maternity-father": ["2026-11-10", "2026-11-20"],
                        "maternity-resumed": ["2026-11-21", "2027-01-18"],
                    }
                },
                "changed": ["maternity", "maternity-father"],
                "changed_notes": ["mother-event"],
                "mention": {"dates": ["2026-11-10", "2026-11-20"]},
                "require": [r"180\s*§\s*1[01]|s\.\s*7\b"],
                "question": None,
            },
        ],
    },
    {
        "id": "stillbirth",
        "about": "stillbirth: 8 weeks after the birth, no parental leave (KP art. 180¹ § 1)",
        "runs": 1,
        "onboarding": {**MOTHER_EXPECTED, "child_born": True, "date": "2026-11-10"},
        "steps": [
            {"event": "timeline_ready", "question": "leave-before-birth"},
            {
                "say": "Nasze dziecko urodziło się martwe.",
                "tools": [{"name": "set_child_loss"}],
                "timeline": {
                    "segments": {"maternity": ["2026-11-10", "2027-01-04"]},
                    "absent": ["parental", "paternity", "parental-father", "parental-deadline"],
                },
                "changed": ["maternity"],
                "changed_notes": ["situation"],
                "mention": {"dates": ["2027-01-04"], "numbers": [8]},
                "sensitive": True,
            },
            {
                "say": "Czy należy mi się jeszcze urlop rodzicielski?",
                "no_tools": ["set_child_loss", "set_children_count"],
                # the timeline shows no parental leave: KP art. 182¹ᵃ § 1 "w celu sprawowania
                # opieki nad dzieckiem"
                "require": [r"opiek\w* nad dzieckiem"],
                "forbid": [r"^\W*tak\b", r"za życiem"],
                "sensitive": True,
            },
        ],
    },
    {
        "id": "death-before-8-weeks",
        "about": "child died on day 51: 8 weeks, but not less than 7 days from the death",
        "runs": 1,
        "onboarding": {**MOTHER_EXPECTED, "child_born": True, "date": "2026-10-01"},
        "steps": [
            {"event": "timeline_ready", "question": "leave-before-birth"},
            {
                "say": "Nie byłam na urlopie przed porodem. Niestety nasz synek zmarł "
                "20 listopada 2026.",
                "tools": [
                    {"name": "set_leave_before_birth", "args": {"weeks": 0}},
                    {"name": "set_child_loss"},
                ],
                "timeline": {
                    "segments": {"maternity": ["2026-10-01", "2026-11-27"]},
                    "absent": ["parental", "parental-father"],
                },
                "mention": {"dates": ["2026-11-27"]},
                "require": [r"7 dni"],
                "sensitive": True,
            },
        ],
    },
    {
        "id": "mother-death",
        "about": "the mother died: the father gets the rest of maternity leave (KP art. 180 § 12)",
        "runs": 1,
        "onboarding": {
            "role": "father",
            "child_born": True,
            "date": "2026-10-01",
            "children_count": 1,
            "work": "employment",
            "earnings": "5k-8k",
        },
        "steps": [
            {"event": "timeline_ready", "question": "mother-work"},
            {
                "say": "Żona pracowała na etacie i nie była na urlopie przed porodem. "
                "Zmarła 10 listopada 2026.",
                "tools": [
                    {"name": "set_mother_work", "args": {"work": "employment"}},
                    {"name": "set_leave_before_birth", "args": {"weeks": 0}},
                    {"name": "set_mother_situation"},
                ],
                "timeline": {
                    "segments": {
                        "maternity": ["2026-10-01", "2026-11-10"],
                        "maternity-father": ["2026-11-11", "2027-02-17"],
                        # he cannot be on paternity leave during his part of maternity leave:
                        # it follows (18.02-3.03.2027); then his parental leave, 41 - 9 = 32
                        # weeks (the mother's 9 cannot be transferred, KP art. 182¹ᵃ § 4)
                        "paternity": ["2027-02-18", "2027-03-03"],
                        "parental-father": ["2027-03-04", "2027-10-13"],
                    }
                },
                "mention": {"dates": ["2026-11-11", "2027-02-17"]},
                "require": [r"180\s*§\s*12|s\.\s*7\b"],
                # the father's 9 weeks after the mother's parental leave (to 1.12.2027): the
                # state before the death was recorded. (30.09.2027 is right: the last day of
                # paternity leave, the day before the first birthday.)
                "forbid": [r"1 grudnia 2027|01\.12\.2027"],
                "sensitive": True,
                "question": "hospital",
            },
        ],
    },
    {
        "id": "card-leave-no-weeks",
        "about": "the plan's card sends 'Chcę urlop przed porodem' without a number of weeks",
        "runs": 2,
        "onboarding": MOTHER_EXPECTED,
        "steps": [
            {
                "say": "Chcę urlop przed porodem",
                # the number of weeks was not given: ask, do not guess
                "no_tools": ["set_leave_before_birth"],
                "timeline": {"segments": {"prenatal-window": ["2027-02-01", "2027-03-14"]}},
                "require": [r"ile tygodni|od kiedy|kiedy chcesz|jak długo|ile wcze"],
                "question": "leave-before-birth",
            }
        ],
    },
    {
        "id": "contract-welcome",
        "about": "the welcome turn alone: must not record the insurance answer itself",
        "runs": 4,
        "onboarding": {**MOTHER_EXPECTED, "work": "contract", "earnings": "under-5k"},
        "steps": [
            {
                "event": "timeline_ready",
                "timeline": {"segments": {"maternity": ["2027-03-15", "2027-08-01"]}},
                "question": "mother-insurance",
            }
        ],
    },
    {
        "id": "death-message-alone",
        "about": "the death of the child as the only fact of the message (no welcome turn)",
        "runs": 2,
        "onboarding": {**MOTHER_EXPECTED, "child_born": True, "date": "2026-10-01"},
        "steps": [
            {
                "say": "Niestety nasz synek zmarł 20 listopada 2026.",
                "tools": [{"name": "set_child_loss"}],
                "timeline": {
                    "segments": {"maternity": ["2026-10-01", "2026-11-27"]},
                    "absent": ["parental", "parental-father", "paternity"],
                },
                "mention": {"dates": ["2026-11-27"]},
                "require": [r"180\s*[¹1]\s*§\s*1\b|s\.\s*6\b"],
                "forbid": [r"przedwcześnie|w szpitalu\?"],
                "sensitive": True,
            }
        ],
    },
    {
        "id": "parental-work-and-split",
        "about": "half-time work extends parental leave; then both parents at once (guide E p. 9, "
        "B.3 p. 7; KP art. 182¹ᵉ § 1, 182¹ᶠ § 2, 182¹ᵃ § 6)",
        "runs": 1,
        "onboarding": MOTHER_EXPECTED,
        "steps": [
            {"event": "timeline_ready", "question": "leave-before-birth"},
            {
                "say": "Przez pierwsze 20 tygodni urlopu rodzicielskiego będę pracować na pół "
                "etatu.",
                "tools": [{"name": "set_parental_work", "args": {"parent": "mother", "weeks": 20}}],
                "timeline": {
                    "segments": {
                        # 32 weeks + 20 x 1/2 = 10 weeks = 294 days: 02.08.2027 + 293 days.
                        "parental-mother-1": ["2027-08-02", "2028-05-21"],
                        # The father's 9 weeks right after her: 22.05.2028 + 62 days.
                        "parental-father": ["2028-05-22", "2028-07-23"],
                    },
                    "absent": ["parental"],
                },
                "mention": {"dates": ["2028-05-21"]},
                "question": "leave-before-birth",
            },
            {
                "say": "Zmiana planu: wezmę 20 tygodni urlopu rodzicielskiego bez pracy, a mąż "
                "w tym samym czasie swoje 9 tygodni.",
                "tools": [{"name": "set_parental_plan"}],
                "timeline": {
                    "segments": {
                        "parental-mother-1": ["2027-08-02", "2027-12-19"],  # 20 weeks
                        "parental-father-1": ["2027-08-02", "2027-10-03"],  # 9 weeks, at once
                    },
                    "absent": ["parental-father"],
                },
                "question": "leave-before-birth",
            },
        ],
    },
    {
        # 270 days from 1.06.2026: 30 + 31 + 31 + 30 + 31 + 30 + 31 (214) + 31 (245) + 25 days
        # of February: the benefit period ends on 25.02.2027; the rehabilitation benefit can
        # follow from 26.02.2027 to 14.03.2027, the day before the due date (ustawa art. 18-19).
        "id": "sick-leave-rehab",
        "about": "sick leave past 270 days in pregnancy, then the rehabilitation benefit",
        "runs": 1,
        "onboarding": MOTHER_EXPECTED,
        "steps": [
            {"event": "timeline_ready", "question": "leave-before-birth"},
            {
                "say": "Pracuję do porodu, ale od 1 czerwca 2026 jestem na zwolnieniu lekarskim "
                "i potrwa ono do porodu. Na etacie pracuję bez przerwy od 1 stycznia 2020.",
                "tools": [
                    {"name": "set_leave_before_birth", "args": {"weeks": 0}},
                    {"name": "set_sick_leave", "args": {"on_sick_leave": True}},
                    {"name": "set_insured_since", "args": {"since": "2020-01-01"}},
                ],
                "timeline": {"markers": {"sick-benefit-limit": "2027-02-25"}},
                "require": [r"rehabilitacyjn"],
            },
            {
                "say": "Złożyłam już wniosek o świadczenie rehabilitacyjne.",
                "tools": [{"name": "set_rehab_benefit", "args": {"status": "applied"}}],
                "timeline": {"segments": {"rehab-benefit": ["2027-02-26", "2027-03-14"]}},
                "changed": ["rehab-benefit"],
                "changed_notes": ["rehab-benefit"],
                "require": [r"orzecznik"],
            },
        ],
    },
    {
        # The mother has no sickness insurance, the father works on a contract of employment:
        # the leave is his, 20 weeks from 2.11.2026 to 21.03.2027 (29 + 31 + 31 + 28 + 21 = 140
        # days), and his share of parental leave, 41 - 9 = 32 weeks, 22.03-31.10.2027. He cannot
        # pass the rest of the leave to the mother: she is not insured (KP art. 183 § 2, 180 § 4).
        "id": "adoption-uninsured-mother",
        "about": "adoption: an uninsured mother, the insured father takes the leave",
        "runs": 1,
        "onboarding": {
            "role": "mother",
            "child_born": True,
            "date": "2024-05-10",
            "children_count": 1,
            "work": "none",
            "taken_in": {"kind": "adoption", "date": "2026-11-02"},
        },
        "steps": [
            {"event": "timeline_ready", "question": "father-work"},
            {
                "say": "Mąż pracuje na etacie.",
                "tools": [{"name": "set_father_work", "args": {"work": "employment"}}],
                "timeline": {
                    "segments": {
                        "adoption-leave": ["2026-11-02", "2027-03-21"],
                        "parental-father": ["2027-03-22", "2027-10-31"],
                    },
                    "absent": ["parental"],
                },
                "mention": {"dates": ["2027-03-21"]},
                "question": "adoption-ruling",
            },
            {
                "say": "Po 14 tygodniach mąż chce wrócić do pracy, a resztę urlopu wezmę ja.",
                "tools": [{"name": "set_leave_handover", "args": {"handed_over": True}}],
                "timeline": {
                    "segments": {"adoption-leave": ["2026-11-02", "2027-03-21"]},
                    "absent": ["adoption-leave-other"],
                },
                "changed_notes": ["handover"],
                "require": [r"nie podlega"],
            },
        ],
    },
    {
        "id": "traps",
        "about": "questions without the data to answer, out-of-scope questions and wrong "
        "premises; nothing may change on the timeline",
        "runs": 1,
        "onboarding": MOTHER_EXPECTED,
        "steps": [
            {"event": "timeline_ready", "question": "leave-before-birth"},
            {
                # Amounts are in scope (section G), but no monthly amount is known yet: the model
                # gives the rate from the source and never invents a sum.
                "say": "Ile pieniędzy dostanę miesięcznie na urlopie macierzyńskim?",
                "no_tools": ["set_monthly_pay"],
                "forbid": [r"\d[\d\s]*,\d\d\s*zł"],
                "require": [r"100\s*%"],
            },
            {
                "say": "Chcę wybrać wariant 81,5%. Na czym on polega?",
                "no_tools": ["set_rate_choice"],
                "require": [r"21 dni", r"81,5"],
            },
            {
                "say": "Do kiedy muszę złożyć wniosek o urlop rodzicielski?",
                "require": [r"21 dni"],
            },
            {
                # Not in the ZUS materials at all.
                "say": "Ile wynosi świadczenie 800 plus i jak je dostać?",
                "out_of_scope": True,
                "forbid": [r"800\s*zł"],
            },
            {
                # A question, not a plan (guide E p. 9): answered from the source, nothing saved.
                "say": "Czy mogę łączyć urlop rodzicielski z pracą na pół etatu?",
                "no_tools": ["set_parental_work", "set_parental_plan"],
                "require": [r"wydłuż"],
            },
            {
                "say": "Przy bliźniętach urlop macierzyński trwa 40 tygodni, prawda?",
                "no_tools": ["set_children_count"],
                "timeline": {"segments": {"maternity": ["2027-03-15", "2027-08-01"]}},
                "mention": {"numbers": [31]},
                "require": [CITES_180_1],
            },
            {
                "say": "Tata może przejąć mój urlop macierzyński już po 8 tygodniach, prawda?",
                "no_tools": ["set_father_takeover", "set_mother_situation"],
                "mention": {"numbers": [14]},
                "require": [r"s\.\s*7\b|180\s*§\s*[45]\b"],
            },
        ],
    },
    {
        "id": "job-loss-bankruptcy",
        "about": "the employer's bankruptcy in pregnancy: the benefit equal to the maternity "
        "benefit until the birth, then the maternity benefit after the insurance ended, no leave "
        "before the birth (guide p. 4; ustawa art. 30 ust. 1 and 3, art. 29a ust. 1)",
        "runs": 1,
        "onboarding": MOTHER_EXPECTED,
        "steps": [
            {"event": "timeline_ready", "question": "leave-before-birth"},
            {
                "say": "Pracodawca ogłosił upadłość i 30 listopada 2026 rozwiązał ze mną umowę "
                "o pracę. Innej pracy mi nie zaproponowano.",
                "tools": [{"name": "set_job_loss"}],
                "timeline": {
                    "segments": {
                        # From the day after the last day of work to the day before the birth.
                        "job-loss-benefit": ["2026-12-01", "2027-03-14"],
                        # The maternity benefit after the insurance ended: 20 weeks from the birth.
                        "maternity": ["2027-03-15", "2027-08-01"],
                        "parental": ["2027-08-02", "2028-03-12"],
                    },
                    "absent": ["prenatal-window", "protection-end", "earliest-start"],
                    "notes": ["job-loss", "insurance"],
                },
                "mention": {"dates": ["2027-03-14"]},
                "require": [r"ZUS|po ustaniu ubezpieczenia"],
                # No leave before the birth to ask about any more.
                "question": "father-work",
            },
        ],
    },
    {
        "id": "money-part-time",
        "about": "the amount of the benefit, then less of it in the weeks of half-time work "
        "(guide G p. 9, E p. 9; ustawa art. 31 ust. 1-2, art. 31 ust. 4a, art. 36 ust. 3)",
        "runs": 1,
        "onboarding": MOTHER_EXPECTED,
        "steps": [
            {"event": "timeline_ready", "question": "leave-before-birth"},
            {
                "say": "Zarabiam 8000 zł brutto miesięcznie, od roku tyle samo.",
                "tools": [{"name": "set_monthly_pay", "args": {"parent": "mother"}}],
                # Base 8000 × (1 − 13,71%) = 6903,20 zł: 100% for maternity leave.
                "require": [r"6\s?903,20"],
                "question": "leave-before-birth",
            },
            {
                "say": "Przez pierwsze 16 tygodni urlopu rodzicielskiego będę pracować na pół "
                "etatu.",
                "tools": [{"name": "set_parental_work", "args": {"parent": "mother", "weeks": 16}}],
                "timeline": {
                    "segments": {
                        # 32 weeks + 16 × 1/2 = 8 weeks = 280 days: 02.08.2027 + 279 days.
                        "parental-mother-1": ["2027-08-02", "2028-05-07"],
                    },
                    "absent": ["parental"],
                },
                # 70% = 4832,24 zł, half of it in the weeks of work: 2416,12 zł a month.
                "require": [r"2\s?416,12"],
                "question": "leave-before-birth",
            },
        ],
    },
    {
        "id": "pay-history-z3",
        "about": "the user types the payer's certificate (Z-3); the calculator computes the base "
        "(ustawa art. 36, 38 ust. 2, 42 ust. 3; Załącznik)",
        "runs": 2,
        "onboarding": MOTHER_EXPECTED,
        "steps": [
            {"event": "timeline_ready", "question": "leave-before-birth"},
            {
                # The right arises on the due date, 15.03.2027 (no leave before it yet): the
                # months are March 2026–February 2027. July: 8 of 23 days, less than half (16 <
                # 23), left out (art. 38 ust. 2 pkt 1). 4 × 7000 + 3 × 9000 = 55 000 / 7 =
                # 7857,14; × (100% − 13,71%) = 6779,93 zł.
                "say": "Przepisuję zarobki brutto z zaświadczenia Z-3: marzec 2026 — 7000 zł, "
                "kwiecień — 7000 zł, maj — 7000 zł, czerwiec — 7000 zł, lipiec — 2400 zł "
                "(przepracowałam 8 z 23 dni, reszta to zwolnienie), sierpień — 9000 zł, "
                "wrzesień — 9000 zł, październik 2026 — 9000 zł.",
                "tools": [{"name": "set_pay_history", "args": {"parent": "mother"}}],
                "no_tools": ["set_monthly_pay"],
                "timeline": {"bases": {"mother": 6779.93}, "notes": ["base-mother"]},
                "changed_notes": ["base-mother"],
                "question": "leave-before-birth",
            },
            {
                # The thirteenth salary for the last year enters as a twelfth (art. 42 ust. 3):
                # 8400 / 12 = 700; 7857,14 + 700 = 8557,14; × 0,8629 = 7383,96 zł. Above the
                # minimum (4806 × 0,8629 = 4147,10), so full time changes nothing.
                "say": "Pracuję na pełny etat i dostaję trzynastkę: za ostatni rok 8400 zł.",
                "tools": [
                    {
                        "name": "set_pay_history",
                        "args": {"parent": "mother", "annual_bonus": 8400, "full_time": True},
                    }
                ],
                "timeline": {"bases": {"mother": 7383.96}},
                "question": "leave-before-birth",
            },
        ],
    },
    {
        # ZADANIA B.0: with the due date known, a question about a premature child must not end
        # with a question about the date. The server adds the interview question itself.
        "id": "premature-question-known-due-date",
        "about": "a what-if question about a premature child while the due date is known: the "
        "closing question is the interview's (leave before the birth), never the date",
        "runs": 2,
        "onboarding": MOTHER_EXPECTED,
        "steps": [
            {"event": "timeline_ready", "question": "leave-before-birth"},
            {
                "say": "Co się zmieni, jeśli dziecko urodzi się przedwcześnie?",
                "no_tools": ["set_due_date", "set_birth_date", "set_hospital_care"],
                "question": "leave-before-birth",
                "forbid": [r"[Kk]iedy (jest|będzie) przewidywany poród", r"[Kk]iedy urodziło się"],
            },
        ],
    },
    {
        # ZADANIA B.4: on Gemini the assistant wrote that the request for maternity leave must be
        # filed with the employer "najpóźniej" by a date. The materials give no deadline for it
        # (CLAUDE.md, open questions): the timeline shows it on the first day of the leave,
        # 2 weeks before 15.03.2027 = 01.03.2027, and only the Labour Code requests have one:
        # parental leave from 19.07.2027 (20 - 2 = 18 weeks after the birth end 18.07.2027),
        # 21 days before = 28.06.2027 (KP art. 182¹ᵈ § 1).
        "id": "no-deadline-maternity-request",
        "about": "asked by when to file the request for maternity leave, the assistant says the "
        "materials give no deadline and never turns the first day of the leave into one",
        "runs": 2,
        "onboarding": MOTHER_EXPECTED,
        "steps": [
            {"event": "timeline_ready", "question": "leave-before-birth"},
            {
                "say": "Chcę zacząć urlop macierzyński 2 tygodnie przed porodem.",
                "tools": [{"name": "set_leave_before_birth", "args": {"weeks": 2}}],
                "timeline": {
                    "segments": {
                        "maternity-prenatal": ["2027-03-01", "2027-03-14"],
                        "maternity": ["2027-03-15", "2027-07-18"],
                        "parental": ["2027-07-19", "2028-02-27"],
                    },
                    "documents": {
                        "maternity-request": "2027-03-01",
                        "parental-request": "2027-06-28",
                    },
                },
                "question": "certificate",
            },
            {
                "say": "Do kiedy najpóźniej muszę złożyć pracodawcy wniosek o urlop macierzyński?",
                "no_tools": ["set_leave_before_birth", "set_due_date", "set_birth_date"],
                "require": [r"nie podaj|nie określaj|nie ma (w nich )?terminu|bez terminu"],
                "forbid": [
                    r"najpóźniej[^.\n]{0,40}(1 marca|01\.03\.2027|2027-03-01|lutego)",
                    r"(musisz|trzeba|należy) (go )?złożyć[^.\n]{0,40}(do|przed) "
                    r"(1 marca|01\.03\.2027|2027-03-01|\d{1,2} lutego)",
                    r"21 lutego 2027",
                ],
                "question": "certificate",
            },
        ],
    },
    {
        # ZADANIA B.8, F8: plans for a goal come from the engine; the model shows the options and
        # leaves the choice to the parents. Hand-computed (tests/test_plans.py): bases 8000 ×
        # 0,8629 = 6903,20 and 6000 × 0,8629 = 5177,40; the whole pool, the mother 32 weeks
        # 30.03-08.11.2027, the father 9 weeks 09.11.2027-10.01.2028. 100% and 70%: 140 × 230,11
        # + 224 × 161,07 + 14 × 172,58 + 63 × 120,81 = 78 322,23 zł; 81,5% (request by
        # 10.11.2026 + 21 days = 01.12.2026): 364 × 187,54 + 10 027,15 = 78 291,71 zł.
        "id": "plans-most-money",
        "about": "the most money: two plans from the engine (100% and 70% or 81,5%), nothing "
        "saved until the parents choose (FUNKCJE F8)",
        "runs": 2,
        "onboarding": {
            "role": "mother",
            "child_born": True,
            "date": "2026-11-10",
            "children_count": 1,
            "work": "employment",
            "payer_size": "over-20",
            "pay": 8000,
            "partner": {"work": "employment", "payer_size": "over-20", "pay": 6000},
            "hospital_care": False,
            "leave_before_birth_weeks": 0,
        },
        "steps": [
            {"event": "timeline_ready"},
            {
                "say": "Jak podzielić urlop rodzicielski, żebyśmy dostali najwięcej pieniędzy?",
                "tools": [{"name": "propose_plans", "args": {"goal": "most-money"}}],
                "no_tools": ["set_parental_plan", "set_rate_choice", "set_father_takeover"],
                "require": [r"78\s?322,23", r"81,5"],
                "forbid": [r"polecam|radzę|najlepiej wybierz|powinniście wybrać"],
                "extra_dates": [
                    "2026-12-01",
                    "2027-03-30",
                    "2027-11-08",
                    "2027-11-09",
                    "2028-01-10",
                ],
            },
        ],
    },
    {
        # ZADANIA B.8, F11: the stress test of an expected child (tests/test_stress.py). A birth
        # 6 weeks early (01.02.2027), 28 days in hospital: 4 weeks of supplementary leave
        # 21.06-18.07.2027 (KP art. 180² § 1 pkt 2, § 3). The work ending on 18.01.2027 for a
        # reason the guide does not name: no insurance on the day of the birth, no maternity
        # benefit (guide p. 3-4, section H).
        "id": "stress-test-expected",
        "about": "what if the child comes early or the job ends: the engine's stress test, no "
        "change saved (FUNKCJE F11)",
        "runs": 2,
        "onboarding": {
            **MOTHER_EXPECTED,
            "payer_size": "over-20",
            "pay": 8000,
            "partner": {"work": "employment", "payer_size": "over-20", "pay": 6000},
        },
        "steps": [
            {"event": "timeline_ready", "question": "leave-before-birth"},
            {
                "say": "Co się stanie z naszym planem, jeśli coś pójdzie nie tak, np. dziecko "
                "urodzi się wcześniej albo stracę pracę?",
                "tools": [{"name": "stress_test"}],
                "no_tools": ["set_birth_date", "set_hospital_care", "set_job_loss"],
                "require": [r"uzupełniając", r"ubezpiecz"],
                "forbid": [r"!"],
                "question": "leave-before-birth",
                "extra_dates": [
                    "2027-01-18",
                    "2027-01-19",
                    "2027-02-01",
                    "2027-02-28",
                    "2027-03-14",
                    "2027-05-10",
                    "2027-06-20",
                    "2027-06-21",
                    "2027-07-18",
                    "2027-07-19",
                ],
            },
        ],
    },
    {
        # ZADANIA B.16: the parents split parental leave on the week tiles and choose 81,5% in
        # the app (PATCH /scenario). The hidden note "Rodzic zmienił w aplikacji…" is in the
        # history: the next turn records nothing again, does not retell the note and does not
        # ask for the split from scratch; asked how to split, it points to the app.
        # The plan by hand: maternity leave 15.03-01.08.2027 (20 weeks, no leave before the
        # birth chosen yet), parental leave from 02.08.2027 (KP art. 182¹ᵃ, guide p. 5-7): the
        # mother 20 weeks = 140 days, 02.08-19.12.2027; the father his 9 weeks at the same time
        # (with_previous, KP art. 182¹ᵃ § 6) = 63 days, 02.08-03.10.2027.
        "id": "app-change-note",
        "about": "the split and the rate changed in the app: nothing recorded again, the note "
        "not retold, the parent pointed to the app instead of asked for the split (B.16)",
        "runs": 2,
        "onboarding": {
            **MOTHER_EXPECTED,
            "payer_size": "over-20",
            "pay": 8000,
            "partner": {"work": "employment", "payer_size": "over-20", "pay": 6000},
        },
        "steps": [
            {"event": "timeline_ready", "question": "leave-before-birth"},
            {
                "patch": {
                    "parental_parts": [
                        {"parent": "mother", "weeks": 20},
                        {"parent": "father", "weeks": 9, "with_previous": True},
                    ],
                    "rate_815": True,
                },
                "say": "Ustawiłam już w aplikacji podział urlopu i stawkę. Co dalej?",
                "no_setters": True,
                "timeline": {
                    "segments": {
                        "parental-mother-1": ["2027-08-02", "2027-12-19"],
                        "parental-father-1": ["2027-08-02", "2027-10-03"],
                    },
                    "absent": ["parental", "parental-father"],
                },
                "forbid": [
                    r"rate_815|parental_parts|with_previous|Rodzic zmienił",
                    r"[Kk]to (weźmie|wykorzysta)|[Ii]le tygodni (weźmie|chce|wykorzyst)",
                    r"w ilu częściach",
                ],
                "question": "leave-before-birth",
            },
            {
                "say": "A jak najlepiej podzielić urlop rodzicielski między mnie a męża?",
                "no_setters": True,
                "require": [r"Jak dzielicie urlop|kafelk|Plan\w* dla Was|w aplikacji"],
                "forbid": [r"[Kk]to (weźmie|wykorzysta)\b[^.?\n]{0,60}\?", r"w ilu częściach"],
                "question": "leave-before-birth",
            },
        ],
    },
]
