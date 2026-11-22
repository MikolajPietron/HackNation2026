"""F9 "Zostawiacie na stole", F10 "Punkty bez powrotu" (engine/leftover.py) and F14 "Nie
przysługuje" z dalszą drogą (engine/no_right.py). Expected dates and amounts computed by hand.

The usual family (as in test_money.py): a child born on 10.11.2026, today 21.11.2026, no leave
before the birth. Maternity leave 10.11.2026-29.03.2027 (140 days), the mother's parental leave
30.03.2027-08.11.2027 (224 days), paternity leave 21.11.2026-04.12.2026 (14 days), the father's
parental leave 09.11.2027-10.01.2028 (63 days). The last days: 81,5% request 10.11.2026 + 21 =
01.12.2026; paternity leave the day before the first birthday, 09.11.2027; parental leave
31.12.2032 (the year the child turns 6).
"""

import datetime as dt

from app.assistant.describe import describe_element, describe_timeline
from app.engine import Scenario, Timeline, build_timeline
from app.engine.models import CaseNote, Leftover, Marker
from app.services.params import load_params

PARAMS = load_params()
TODAY = dt.date(2026, 11, 21)
BORN = dt.date(2026, 11, 10)
DUE = dt.date(2027, 3, 15)
FAMILY = {"role": "mother", "work": "employment", "children_count": 1}
PAY = {"mother_pay": 8000, "father_work": "employment", "father_pay": 6000}


def born(**answers: object) -> Timeline:
    scenario = Scenario.model_validate(
        {**FAMILY, "child_born": True, "birth_date": BORN, "leave_before_birth_weeks": 0} | answers
    )
    return build_timeline(scenario, PARAMS, TODAY)


def expecting(**answers: object) -> Timeline:
    scenario = Scenario.model_validate({**FAMILY, "child_born": False, "due_date": DUE} | answers)
    return build_timeline(scenario, PARAMS, TODAY)


def taken_in(**answers: object) -> Timeline:
    scenario = Scenario.model_validate(
        {**FAMILY, "child_born": True, "taken_in": "foster", "taken_in_on": "2026-11-02"}
        | {"birth_date": "2024-05-10"}
        | answers
    )
    return build_timeline(scenario, PARAMS, TODAY)


def marker(t: Timeline, marker_id: str) -> Marker:
    found = t.element(marker_id)
    assert isinstance(found, Marker), marker_id
    return found


def left(t: Timeline) -> dict[str, Leftover]:
    return {item.id: item for item in t.left_on_table}


def note(t: Timeline, note_id: str) -> CaseNote:
    return next(n for n in t.notes if n.id == note_id)


def note_ids(t: Timeline) -> list[str]:
    return [n.id for n in t.notes]


# F10: points of no return.


def test_the_three_points_of_no_return_count_down_from_today() -> None:
    """21.11.2026 -> 01.12.2026: 10 days; -> 09.11.2027: 365 - 12 = 353 days; -> 31.12.2032:
    6 years with two 29 Februaries (2192 days) to 21.11.2032, then 40 days: 2232."""
    t = born(**PAY)
    rate, paternity, parental = (
        marker(t, "rate-815-deadline"),
        marker(t, "paternity-deadline"),
        marker(t, "parental-deadline"),
    )
    assert (rate.date, paternity.date, parental.date) == (
        dt.date(2026, 12, 1),
        dt.date(2027, 11, 9),
        dt.date(2032, 12, 31),
    )
    assert [m.irreversible.days_left for m in (rate, paternity, parental) if m.irreversible] == [
        10,
        353,
        2232,
    ]
    assert rate.irreversible is not None and paternity.irreversible is not None
    assert rate.irreversible.lost.startswith("Wybór zasiłku 81,5% za cały urlop macierzyński")
    assert {s.article for s in rate.irreversible.sources if s.doc == "ustawa"} == {
        "art. 30a ust. 1"
    }
    assert "prawo do niego wygasa" in paternity.irreversible.lost
    assert any("prawo do tego urlopu wygasa" in s.quote for s in paternity.irreversible.sources)
    assert parental.irreversible is not None
    assert any(s.article == "art. 182¹ᶜ" for s in parental.irreversible.sources)
    # Every quote is one the marker itself already shows.
    for m in (rate, paternity, parental):
        assert m.irreversible is not None
        assert all(s in m.sources for s in m.irreversible.sources)
    # Other days end nothing for good.
    for m in t.markers:
        if m.id not in ("rate-815-deadline", "paternity-deadline", "parental-deadline"):
            assert m.irreversible is None, m.id


def test_a_passed_point_of_no_return_counts_below_zero() -> None:
    """Born 01.10.2026: the 81,5% request ended on 22.10.2026, 30 days before today."""
    t = born(birth_date=dt.date(2026, 10, 1), mother_pay=7000)
    rate = marker(t, "rate-815-deadline")
    assert rate.irreversible is not None and rate.irreversible.days_left == -30
    assert "left-rate-815" not in left(t)  # nothing to do about it any more


def test_points_of_no_return_of_a_child_taken_in() -> None:
    """Foster family, taken in 02.11.2026: the request for 81,5% within 21 days, 23.11.2026
    (art. 30a ust. 2); parental leave until the end of 2030 (born 10.05.2024, turns 6 in 2030).
    Adoption with the ruling final on 15.11.2026: paternity leave until 14.11.2027."""
    t = taken_in(mother_pay=7000)
    rate = marker(t, "rate-815-deadline")
    assert rate.date == dt.date(2026, 11, 23)
    assert rate.irreversible is not None and rate.irreversible.days_left == 2
    assert "po przyjęciu dziecka na wychowanie" in rate.irreversible.lost
    assert [s.article for s in rate.irreversible.sources] == ["art. 30a ust. 2"]
    assert marker(t, "parental-deadline").date == dt.date(2030, 12, 31)
    adopted = taken_in(
        taken_in="adoption",
        role="father",
        adoption_final=True,
        adoption_final_on="2026-11-15",
    )
    paternity = marker(adopted, "paternity-deadline")
    assert paternity.date == dt.date(2027, 11, 14)
    assert paternity.irreversible is not None
    quotes = " ".join(s.quote for s in paternity.irreversible.sources)
    assert "od uprawomocnienia się przysposobienia" in quotes and "wygasa" in quotes
    assert not any("wyłączne prawo ojca" in s.quote for s in paternity.irreversible.sources)


# F9: what the family would leave on the table.


def test_the_usual_family_leaves_four_things_on_the_table_soonest_first() -> None:
    """Base of the mother 8000 × 0,8629 = 6903,20 zł, of the father 6000 × 0,8629 = 5177,40 zł.
    Paternity 100%: 5177,40 / 30 = 172,58; × 14 = 2416,12 zł. The mother's parental leave, 70%:
    4832,24 / 30 = 161,07; × 224 = 36 079,68 zł. The father's 9 weeks, 70%: 3624,18 / 30 =
    120,81; × 63 = 7611,03 zł. The last day to start: 09.11.2027 - 13 days = 27.10.2027;
    31.12.2032 - 223 days = 22.05.2032; 31.12.2032 - 62 days = 30.10.2032.
    81,5%: 100% and 70% give 140 × 230,11 + 36 079,68 = 68 295,08 zł; 81,5% gives 6903,20 ×
    0,815 / 30 = 187,54 a day, × 364 = 68 264,56 zł: no more, so 0 is lost."""
    t = born(**PAY)
    items = left(t)
    assert list(items) == [
        "left-rate-815",
        "left-paternity",
        "left-parental",
        "left-parental-father",
    ]
    paternity, mothers, fathers = (
        items["left-paternity"],
        items["left-parental"],
        items["left-parental-father"],
    )
    assert (paternity.kind, paternity.parent, paternity.days, paternity.amount) == (
        "leave",
        "father",
        14,
        2416.12,
    )
    assert (paternity.last_day, paternity.start_by) == (dt.date(2027, 11, 9), dt.date(2027, 10, 27))
    assert (paternity.segment_id, paternity.marker_id) == ("paternity", "paternity-deadline")
    assert "prawo do niego wygasa" in paternity.text
    assert (mothers.parent, mothers.days, mothers.amount) == ("mother", 224, 36079.68)
    assert (mothers.last_day, mothers.start_by) == (dt.date(2032, 12, 31), dt.date(2032, 5, 22))
    assert mothers.text.startswith("Mama może jeszcze wykorzystać 32 tyg. urlopu rodzicielskiego")
    assert (fathers.parent, fathers.days, fathers.amount) == ("father", 63, 7611.03)
    assert fathers.start_by == dt.date(2032, 10, 30)
    assert fathers.text.startswith(
        "9 tyg. urlopu rodzicielskiego należy wyłącznie do taty: nie można ich przenieść na mamę."
    )
    assert any(s.article == "art. 182¹ᵃ § 4" for s in fathers.sources)
    rate = items["left-rate-815"]
    assert (rate.kind, rate.parent, rate.days, rate.amount, rate.start_by) == (
        "choice",
        "mother",
        None,
        0.0,
        None,
    )
    assert (rate.last_day, rate.marker_id) == (dt.date(2026, 12, 1), "rate-815-deadline")
    assert "68 295,08 zł przy 100% i 70% albo 68 264,56 zł przy 81,5%" in rate.text
    assert "Bez wniosku zasiłek wynosi 100% za urlop macierzyński i 70%" in rate.text


def test_without_amounts_the_items_have_no_money() -> None:
    t = born()
    assert [item.amount for item in t.left_on_table] == [None, None, None]
    assert "left-rate-815" not in left(t)  # money.py draws the 81,5% deadline with the amounts


def test_after_choosing_81_5_the_request_is_still_to_file() -> None:
    """With the request the mother's parental leave is paid 187,54 a day: × 224 = 42 008,96 zł;
    the father's own 9 weeks stay at 70%."""
    t = born(**PAY, rate_815=True)
    items = left(t)
    assert items["left-rate-815"].text.startswith(
        "Mama wybiera 81,5%: pisemny wniosek trzeba złożyć do 1 grudnia 2026"
    )
    assert items["left-parental"].amount == 42008.96
    assert items["left-parental-father"].amount == 7611.03
    assert "left-rate-815" not in left(born(**PAY, rate_815=False))


def test_paternity_leave_cut_by_its_last_day() -> None:
    """Born 30.11.2025: the last day is 29.11.2026, so 9 days are left, from today."""
    item = left(born(birth_date=dt.date(2025, 11, 30)))["left-paternity"]
    assert (item.days, item.start_by, item.last_day) == (9, TODAY, dt.date(2026, 11, 29))


def test_an_option_drawn_in_the_past_is_counted_from_today() -> None:
    """Born 01.06.2020, the mother does not work: the father's parental leave fits only from
    today to 31.12.2026, 41 days."""
    t = born(birth_date=dt.date(2020, 6, 1), role="father", mother_work="none")
    item = left(t)["left-parental-father"]
    assert (item.days, item.start_by, item.last_day) == (41, TODAY, dt.date(2026, 12, 31))
    assert item.text == (
        "Tata może jeszcze wykorzystać 41 dni urlopu rodzicielskiego, najpóźniej do 31 grudnia "
        "2026."
    )


def test_supplementary_leave_only_right_after_maternity_leave() -> None:
    """Born 01.10.2026 in the 28-37th week, 20 days in hospital: 3 weeks. Maternity leave ends
    01.10.2026 + 139 days = 17.02.2027, so supplementary leave runs 18.02-10.03.2027."""
    hospital = {"hospital_care": True, "birth_week": "28-37", "birth_weight_up_to_1000g": False}
    stays = {"hospital_stays": [{"start": "2026-10-01", "end": "2026-10-20"}]}
    item = left(born(birth_date=dt.date(2026, 10, 1), **hospital, **stays))["left-supplementary"]
    assert (item.parent, item.days, item.start_by, item.last_day) == (
        None,
        21,
        dt.date(2027, 2, 18),
        dt.date(2027, 3, 10),
    )
    assert "bezpośrednio po urlopie macierzyńskim, czyli od 18 lutego 2027" in item.text
    assert any(s.section == "C" for s in item.sources)


def test_weeks_a_plan_leaves_out() -> None:
    """41 weeks for both; the plan: the mother 20 weeks. Her option is replaced, the father's
    9 weeks still shown: 41 - 20 - 9 = 12 weeks (84 days) nobody planned; the last day to start
    them 31.12.2032 - 83 days = 09.10.2032."""
    t = born(parental_parts=[{"parent": "mother", "weeks": 20}])
    pool = left(t)["left-parental-pool"]
    assert (pool.parent, pool.days, pool.amount, pool.start_by) == (
        None,
        84,
        None,
        dt.date(2032, 10, 9),
    )
    assert pool.text.startswith("W planie urlopu rodzicielskiego zostało 12 tyg.")
    assert "left-parental" not in left(t) and "left-parental-father" in left(t)


def test_weeks_a_plan_leaves_out_some_of_them_the_fathers_alone() -> None:
    """The mother 20 weeks, the father 5: 41 - 25 = 16 weeks left, of them 9 - 5 = 4 weeks only
    the father can use."""
    t = born(parental_parts=[{"parent": "mother", "weeks": 20}, {"parent": "father", "weeks": 5}])
    pool = left(t)["left-parental-pool"]
    assert pool.days == 112
    assert "4 tyg. z nich może wykorzystać tylko tata" in pool.text
    # A plan that uses the whole pool leaves nothing out.
    whole = [{"parent": "mother", "weeks": 32}, {"parent": "father", "weeks": 9}]
    assert "left-parental-pool" not in left(born(parental_parts=whole))


def test_a_parent_who_is_not_an_employee_gets_the_benefit_for_that_time() -> None:
    t = born(work="contract", mother_insured=True)
    assert "Mama nie jest pracownicą" in left(t)["left-parental"].text
    assert any(s.page == 4 for s in left(t)["left-parental"].sources)


def test_nothing_on_the_table_after_a_loss_or_the_mothers_death() -> None:
    assert born(losses=[{"stillborn": True}]).left_on_table == []
    twins = born(children_count=2, losses=[{"died_on": "2026-11-15"}])
    assert twins.left_on_table == []
    after = born(
        birth_date=dt.date(2026, 10, 1), mother_event={"kind": "death", "start": "2026-11-15"}
    )
    assert after.left_on_table == []


def test_after_the_mother_abandoned_the_child_her_options_are_not_listed() -> None:
    """Born 05.01.2026, the mother left on 01.08.2026 during her parental leave (cut to that
    day): only the father's paternity leave (until 04.01.2027) and his 9 weeks are left."""
    t = born(
        birth_date=dt.date(2026, 1, 5),
        father_work="employment",
        mother_event={"kind": "abandonment", "start": "2026-08-01"},
    )
    assert "parental" in [s.id for s in t.segments]  # still drawn, cut, on her lane
    assert list(left(t)) == ["left-paternity", "left-parental-father"]
    assert left(t)["left-paternity"].last_day == dt.date(2027, 1, 4)


# F14: no right, and what then.


def test_a_mother_not_registered_for_the_voluntary_insurance_before_the_birth() -> None:
    """Due 15.03.2027: paternity leave 15-28.03.2027 (until 14.03.2028), then the father's
    parental leave 29.03.2027 + 223 days = 07.11.2027."""
    t = expecting(work="contract", mother_insured=False)
    way = note(t, "insurance-way")
    assert note_ids(t)[note_ids(t).index("insurance") + 1] == "insurance-way"
    assert (way.kind, way.title) == ("risk", "Zasiłek mamy: co zamiast i co zrobić")
    assert way.text.startswith("Co zamiast: Jeśli mama nie będzie ubezpieczona w dniu porodu")
    assert "na osi 32 tyg., od 29 marca 2027 do 7 listopada 2027" in way.text
    assert "można go wykorzystać do 14 marca 2028" in way.text
    todo = "Co zrobić, żeby przysługiwał: Przy umowie zlecenia ubezpieczenie chorobowe jest"
    assert todo in way.text
    assert "trzeba się do niego zgłosić" in way.text
    quotes = [s.quote for s in way.sources]
    assert any("niezgłoszenie się" in q for q in quotes)  # section H, risk 3
    assert any("matka na dzień porodu nie była ubezpieczona" in q for q in quotes)  # B.3
    # The ZUS Poradnik (page 35): the parental allowance instead, without an amount.
    assert "ma świadczenie rodzicielskie albo uposażenie macierzyńskie" in way.text
    assert "Kwot i warunków tych świadczeń nie ma w naszych materiałach" in way.text
    assert any(s.doc == "poradnik" and s.page == 35 for s in way.sources)
    assert way.text.index("świadczenie rodzicielskie") < way.text.index("Co zrobić")


def test_after_the_birth_only_what_instead() -> None:
    t = born(work="none")
    way = note(t, "insurance-way")
    assert way.title == "Zasiłek mamy: co zamiast"
    assert "Mama nie była ubezpieczona w dniu porodu, więc zasiłek" in way.text
    assert "Co zrobić" not in way.text


def test_a_mother_who_does_not_work_is_warned_about_a_contract_only_for_the_benefit() -> None:
    way = note(expecting(work="none"), "insurance-way")
    assert "obowiązkowemu (np. z umowy o pracę) albo dobrowolnemu" in way.text
    assert "dla pozoru" in way.text
    assert any(s.section == "H.1" for s in way.sources)


def test_a_job_that_ended_before_the_birth_and_a_fixed_term_contract() -> None:
    t = expecting(job_loss={"ended_on": "2026-11-30", "reason": "other"})
    way = note(t, "insurance-way")
    assert note_ids(t)[note_ids(t).index("job-loss") + 1] == "insurance-way"
    assert "na czas określony albo na okres próbny dłuższy niż miesiąc" in way.text
    articles = {s.article for s in way.sources}
    assert {"art. 177 § 3", "art. 30 ust. 4"} <= articles


def test_both_parents_uninsured_after_the_birth() -> None:
    """After the birth only the parental allowance instead for the mother (ZUS Poradnik, page
    35), nothing to do; the father who does not work: the same instead, and paternity leave if
    he starts work before the child completes 12 months (09.11.2027)."""
    t = born(work="none", father_work="none")
    mother = note(t, "insurance-way")
    assert mother.title == "Zasiłek mamy: co zamiast"
    assert mother.text.startswith("Co zamiast: Kto z powodu swojej sytuacji zawodowej nie może")
    assert "Co zrobić" not in mother.text
    assert [s.doc for s in mother.sources] == ["poradnik", "poradnik"]
    way = note(t, "father-way")
    assert note_ids(t)[note_ids(t).index("father") + 1] == "father-way"
    assert way.title == "Zasiłek taty: co zamiast i co zrobić"
    assert "świadczenie rodzicielskie albo uposażenie macierzyńskie" in way.text
    assert "rozpoczął pracę po narodzinach dziecka" in way.text
    assert "najpóźniej do 9 listopada 2027" in way.text
    assert any("rozpoczął pracę" in s.quote for s in way.sources)
    # Once paternity leave can no longer start, the allowance is what is left to say.
    late = born(work="none", father_work="none", birth_date=dt.date(2025, 1, 10))
    assert note(late, "father-way").title == "Zasiłek taty: co zamiast"


def test_a_father_not_registered_for_the_voluntary_insurance() -> None:
    way = note(born(father_work="contract", father_insured=False), "father-way")
    assert "Przy umowie zlecenia ubezpieczenie chorobowe jest dobrowolne" in way.text
    assert any(s.page == 10 and "nie ma uprawnień do zasiłków" in s.quote for s in way.sources)


def test_no_way_point_where_there_is_a_right_or_after_a_loss() -> None:
    insured = born(father_work="employment")
    assert not {"insurance-way", "father-way", "taken-in-way"} & set(note_ids(insured))
    stillborn = born(work="none", losses=[{"stillborn": True}])
    assert note_ids(stillborn) == ["situation", "insurance"]


def test_a_foster_child_past_seven_and_postponed_schooling() -> None:
    """Born 01.01.2018, taken in 02.11.2026: 7 on 01.01.2025, too old; 10 only on 01.01.2028."""
    t = taken_in(birth_date="2018-01-01")
    way = note(t, "taken-in-way")
    assert note_ids(t)[note_ids(t).index("taken-in-leave") + 1] == "taken-in-way"
    assert "odroczeniu obowiązku szkolnego" in way.text and "10 lat" in way.text
    assert any(s.article == "art. 183 § 1" for s in way.sources)
    assert "taken-in-way" not in note_ids(taken_in(birth_date="2018-01-01", school_postponed=False))
    # Adoption: 14 is the limit, nothing to add.
    old = taken_in(taken_in="adoption", birth_date="2012-01-01")
    assert "taken-in-way" not in note_ids(old)


# The assistant gets the same.


def test_the_assistant_reads_the_points_of_no_return_and_what_is_left() -> None:
    t = born(**PAY)
    text = describe_timeline(t)
    assert "Punkty bez powrotu (z kalkulatora):" in text
    assert "- [paternity-deadline] 09.11.2027: Urlop ojcowski: jeśli tata nie wykorzysta" in text
    assert "- [left-parental] do 31.12.2032: Mama może jeszcze wykorzystać 32 tyg." in text
    assert "Kwota: 36 079,68 zł." in text
    assert "Punkt bez powrotu: Urlop ojcowski" in describe_element(marker(t, "paternity-deadline"))
