"""Applications and protection: what to file, where and by when, who pays the benefit, and the
special protection of employees. Guide A.4 "Dokumenty stanowiące podstawę do ustalenia zasiłku"
(page 6), page 1 with footnote 1 (who pays), the forms on page 12 and section I "Szczególna
ochrona" (page 10), with the Labour Code provisions on the requests and their deadlines (art. 177,
art. 180 § 8, § 9 and § 16, art. 180² § 4-5, art. 182¹ᵈ § 1, art. 182³ § 2).

Applied last, on the finished timeline (`add_applications`, before the case notes):
- who pays: every benefit period says it. The payer of contributions pays when it reports more
  than 20 people to sickness insurance, otherwise ZUS; with her own business the mother files
  ZAM straight with ZUS, so ZUS pays;
- requests as documents: an employee asks the employer for each leave (one request may cover
  maternity and parental leave right after it); the Labour Code deadlines are counted back from
  the leave; a mother who is not an employee files ZAM (on a contract of mandate the payer
  determines the benefit or ZUS does, with Z-3a from the payer);
- protection: for an employed mother, the last day of the special protection her leave on the
  timeline gives, and the extension of a fixed-term contract until the birth;
- sick leave in pregnancy (guide page 3, pregnancy.py draws the periods): e-ZLA goes straight to
  ZUS and to the employer's profile; an employee informs her employer of the absence; the
  employer pays its days (wynagrodzenie chorobowe), then the sickness benefit is paid by the
  payer or ZUS by the same rule of more than 20 insured, the payer sending Z-3 (ZAS-12 for a
  further period) or, on a contract of mandate, Z-3a; with a business ZAS-53 goes to ZUS;
- the benefit after losing the job (guide page 4): after an unlawful termination, the final court
  judgment it needs.
  timeline gives, and the extension of a fixed-term contract until the birth (after which the
  maternity benefit is due after the insurance ended, ustawa art. 30 ust. 4);
- a mother whose employment ended in pregnancy and who has the benefit after it (ustawa art. 30
  ust. 1, after_insurance.py) is no longer an employee: she files ZAM with ZUS, ZUS pays (art. 61
  ust. 1 pkt 2 lit. d), and no protection marker is drawn.

Our readings (CLAUDE.md, open questions):
- "w terminie nie krótszym niż N dni przed" a day: the request is filed N days before that day at
  the latest (the 21st day before the first day of parental leave, say);
- the materials give no deadline for the request for maternity leave or for ZAM: shown on the day
  the leave (the benefit) starts;
- for an option the parents still choose (parental, paternity leave) whose deadline has passed for
  the start drawn on the timeline: the request is due today, and its rule says from which day a
  request filed today is in time; for a fixed day (supplementary leave, taking over) the passed
  deadline stays where it was;
- the guide says where a mother who is not an employee files ZAM; we show the same for the father;
- with her own business the guide sends ZAM straight to ZUS: we say that ZUS pays;
- sick leave: the guide sends an employee to the Labour Code for informing the employer, and
  those provisions are not in the materials: we show it on the first day of the sick leave, and
  only while that day is ahead; the documents for the sickness benefit (contract, business) have
  no deadline in the materials: shown on the day the benefit starts, like ZAM; with a business
  ZAS-53 goes to ZUS, so ZUS pays the sickness benefit too;
- the guide does not say by when the court judgment must come, nor what to file for the benefit
  after losing the job or who pays it: the judgment is shown on the day the benefit would start,
  the rest is not on the timeline.
"""

import datetime as dt
from typing import Literal

from app.engine.after_insurance import after_job_loss
from app.engine.draft import DAY, merge_sources
from app.engine.insurance import NOT_INSURED, coverage, father_coverage
from app.engine.models import (
    CaseNote,
    Document,
    Marker,
    Scenario,
    Segment,
    SourceRef,
    Timeline,
    Work,
)
from app.engine.params import Params
from app.engine.pregnancy import JOB_LOSS_SEGMENT, SEGMENT_IDS
from app.engine.wording import fmt, long_date

Parent = Literal["mother", "father"]
Payer = Literal["payer", "zus", "payer-or-zus"]

MOTHER_LEAVE = ("maternity-prenatal", "maternity", "maternity-resumed", "supplementary", "parental")
"""The mother's periods of leave (or of the benefit for that time)."""
BENEFIT_PERIODS = (*MOTHER_LEAVE, "prenatal-window")
REQUESTS = (
    "maternity-request",
    "supplementary-request",
    "parental-request",
    "maternity-resignation",
    "maternity-father-request",
    "paternity-request",
    "parental-father-request",
    "father-benefit-request",
)
"""The requests for leave and the maternity benefit this module adds, by id."""
SICK_DOCUMENTS = ("sick-leave-notice", "sick-benefit-request")
"""Sick leave in pregnancy: informing the employer; the documents for the sickness benefit."""
COURT_JUDGMENT = "court-judgment"
"""The final court judgment the benefit after an unlawful termination needs."""
SICK_PAY, SICK_BENEFIT = SEGMENT_IDS["employer"], SEGMENT_IDS["benefit"]
WORKING = ("employment", "contract", "business")

WHOSE = {"mother": "mamy", "father": "taty"}
WHO = {"mother": "Mama", "father": "Tata"}


def add_applications(timeline: Timeline, scenario: Scenario, params: Params) -> None:
    """Who pays on every benefit period, the requests, the end of the protection."""
    today = timeline.today
    timeline.segments = [_with_payer(s, scenario, params) for s in timeline.segments]
    timeline.documents += _requests(scenario, timeline, params, today)
    timeline.documents += _sick_documents(scenario, timeline, params, today)
    timeline.documents += _job_loss_documents(scenario, timeline, params, today)
    protection = _protection_end(scenario, timeline, params)
    if protection is not None:
        timeline.markers.append(protection)
    _fixed_term(scenario, timeline, params)
    timeline.markers.sort(key=lambda m: m.date)
    timeline.assumptions += _assumptions(scenario, timeline)


# Who pays.


def _work(scenario: Scenario, parent: Parent) -> Work | None:
    return scenario.mothers_work if parent == "mother" else scenario.fathers_work


def _covered(scenario: Scenario, parent: Parent) -> bool:
    cover = coverage(scenario) if parent == "mother" else father_coverage(scenario)
    return cover not in NOT_INSURED and _work(scenario, parent) in WORKING


def who_pays(scenario: Scenario, parent: Parent) -> Payer:
    if _work(scenario, parent) == "business" or _after_job_loss(scenario, parent):
        return "zus"
    size = scenario.mother_payer_size if parent == "mother" else scenario.father_payer_size
    match size:
        case "over-20":
            return "payer"
        case "up-to-20":
            return "zus"
        case _:
            return "payer-or-zus"


def _after_job_loss(scenario: Scenario, parent: Parent) -> bool:
    """The mother has the benefit after her employment ended in pregnancy (ustawa art. 30)."""
    return parent == "mother" and after_job_loss(scenario) is not None


def _payer_name(work: Work | None) -> str:
    return "pracodawca" if work == "employment" else "płatnik składek (zleceniodawca)"


def payer_line(scenario: Scenario, parent: Parent, params: Params) -> tuple[str, list[SourceRef]]:
    """One sentence: who pays this parent's benefit, and its sources."""
    a = params.applications
    work = _work(scenario, parent)
    whose = WHOSE[parent]
    his = "jej" if parent == "mother" else "jego"
    limit = a.payer_more_than_insured.value
    payer = _payer_name(work)
    short = "pracodawca" if work == "employment" else "zleceniodawca"
    # The guide names the certificate the payer sends to ZUS only for the mother (page 6).
    certificate = "Z-3a" if work == "contract" else "Z-3"
    mothers = parent == "mother"
    request = a.employer_pays_or_z3.sources if work == "employment" else a.contract_zam.sources
    if _after_job_loss(scenario, parent):
        return (
            "Zasiłek mamy wypłaca ZUS: przysługuje jej za okres po ustaniu ubezpieczenia.",
            merge_sources(params.pregnancy.zus_after_insurance.sources),
        )
    match who_pays(scenario, parent):
        case "zus" if work == "business":
            return (
                f"Zasiłek {whose} wypłaca ZUS: przy własnej firmie wniosek o zasiłek macierzyński "
                "(ZAM) składa się bezpośrednio do ZUS.",
                merge_sources(a.non_employee_zam.sources, a.paid_by_payer_or_zus.sources),
            )
        case "payer":
            text = (
                f"Zasiłek {whose} wypłaca {his} {payer}: zgłasza do ubezpieczenia chorobowego "
                f"więcej niż {limit} osób."
            )
        case "zus":
            sends = (
                f", więc przesyła do ZUS zaświadczenie płatnika składek {certificate}"
                if mothers
                else ""
            )
            text = (
                f"Zasiłek {whose} wypłaca ZUS: {his} {payer} zgłasza do ubezpieczenia chorobowego "
                f"nie więcej niż {limit} osób{sends}."
            )
        case _:
            sends = (
                f", a {short} przesyła do ZUS zaświadczenie płatnika składek {certificate}"
                if mothers
                else ""
            )
            text = (
                f"Zasiłek {whose} wypłaca {his} {payer}, jeśli zgłasza do ubezpieczenia "
                f"chorobowego więcej niż {limit} osób; jeśli nie, wypłaca go ZUS{sends}."
            )
    return text, merge_sources(
        a.paid_by_payer_or_zus.sources,
        a.payer_more_than_insured.sources,
        request if mothers else [],
    )


def _with_payer(segment: Segment, scenario: Scenario, params: Params) -> Segment:
    """Every benefit period says who pays it: the mother's (her lane) or the father's."""
    if _is_sick_benefit(segment) and scenario.mothers_work in WORKING:
        line, sources = sick_payer_line(scenario, params)
        return segment.model_copy(
            update={
                "details": [*segment.details, line],
                "sources": merge_sources(segment.sources, sources),
            }
        )
    if segment.lane == "mother" and segment.id in BENEFIT_PERIODS:
        parent: Parent = "mother"
    elif segment.lane == "father":
        parent = "father"
    else:
        return segment
    if not _covered(scenario, parent):
        return segment
    line, sources = payer_line(scenario, parent, params)
    return segment.model_copy(
        update={
            "details": [*segment.details, line],
            "sources": merge_sources(segment.sources, sources),
        }
    )


# Sick leave in pregnancy and the benefit after losing the job (guide pages 3-4).


def _is_sick(segment: Segment) -> bool:
    """A period of sick leave in pregnancy: the employer's days or the sickness benefit."""
    return segment.lane == "mother" and segment.id.startswith((SICK_PAY, SICK_BENEFIT))


def _is_sick_benefit(segment: Segment) -> bool:
    return segment.lane == "mother" and segment.id.startswith(SICK_BENEFIT)


def sick_payer_line(scenario: Scenario, params: Params) -> tuple[str, list[SourceRef]]:
    """Who pays the mother's sickness benefit in pregnancy, and its sources: the same rule of
    more than 20 insured as for every benefit (page 1, footnote 1), the payer's certificate from
    page 3. Only for a mother whose work is known."""
    a = params.applications
    work = scenario.mothers_work
    if work == "business":
        return (
            "Zasiłek chorobowy mamy wypłaca ZUS: przy własnej firmie wniosek o zasiłek chorobowy "
            "(ZAS-53) składa się do ZUS.",
            merge_sources(a.sick_business.sources, a.paid_by_payer_or_zus.sources),
        )
    limit = a.payer_more_than_insured.value
    if work == "employment":
        payer, short, rule = "pracodawca", "pracodawca", a.sick_employee_payer
        certificate = "Z-3 (na dalszy okres ZAS-12)"
    else:
        payer, short, rule = "płatnik składek (zleceniodawca)", "zleceniodawca", a.sick_contract
        certificate = "Z-3a"
    match who_pays(scenario, "mother"):
        case "payer":
            text = (
                f"Zasiłek chorobowy mamy wypłaca jej {payer} na podstawie zaświadczenia e-ZLA: "
                f"zgłasza do ubezpieczenia chorobowego więcej niż {limit} osób."
            )
        case "zus":
            text = (
                f"Zasiłek chorobowy mamy wypłaca ZUS: jej {payer} zgłasza do ubezpieczenia "
                f"chorobowego nie więcej niż {limit} osób, więc przekazuje do ZUS wniosek "
                f"o wypłatę zasiłku, zaświadczenie płatnika składek {certificate}."
            )
        case _:
            text = (
                f"Zasiłek chorobowy mamy wypłaca jej {payer} na podstawie zaświadczenia e-ZLA, "
                f"jeśli zgłasza do ubezpieczenia chorobowego więcej niż {limit} osób; jeśli nie, "
                f"{short} przekazuje do ZUS wniosek o wypłatę zasiłku, zaświadczenie płatnika "
                f"składek {certificate}, i zasiłek wypłaca ZUS."
            )
    return text, merge_sources(
        rule.sources, a.paid_by_payer_or_zus.sources, a.payer_more_than_insured.sources
    )


def _sick_documents(
    scenario: Scenario, timeline: Timeline, params: Params, today: dt.date
) -> list[Document]:
    """Guide page 3. An employee informs her employer of the absence (shown while the first day
    of the sick leave is ahead); on a contract of mandate she files the documents for the benefit
    with ZUS or the payer, with a business ZAS-53 with ZUS (shown while the benefit lasts)."""
    work = scenario.mothers_work
    sick = [s for s in timeline.segments if _is_sick(s)]
    if work not in WORKING or not sick:
        return []
    a = params.applications
    if work == "employment":
        start = scenario.sick_leave_start
        if start is None or start < today:
            return []
        rule = [
            "Mama pracuje na umowie o pracę, więc powinna poinformować pracodawcę o nieobecności "
            "w pracy zgodnie z przepisami Kodeksu pracy. Pokazujemy to na pierwszy dzień "
            "zwolnienia.",
            "Zaświadczenie lekarskie e-ZLA trafia bezpośrednio do ZUS i na profil pracodawcy "
            "na PUE/eZUS.",
        ]
        sources = [a.sick_inform_employer.sources, a.sick_e_zla.sources]
        if any(_is_sick_benefit(s) for s in sick):
            line, line_sources = sick_payer_line(scenario, params)
            rule.append(line)
            sources.append(line_sources)
        return [
            Document(
                id="sick-leave-notice",
                label="Nieobecność: daj znać pracodawcy",
                title="Informacja dla pracodawcy o nieobecności w pracy",
                needed_by=start,
                done=False,
                rule=" ".join(rule),
                segment_id=sick[0].id,
                sources=merge_sources(*sources),
            )
        ]
    benefit = [s for s in sick if _is_sick_benefit(s) and s.end >= today]
    if not benefit:
        return []
    first = min(benefit, key=lambda s: s.start)
    line, line_sources = sick_payer_line(scenario, params)
    if work == "business":
        title, label = "Wniosek o zasiłek chorobowy (ZAS-53)", "Wniosek ZAS-53"
        rule = [
            "Mama prowadzi własną firmę: na zwolnieniu powinna powstrzymać się od pracy "
            "zawodowej, a aby dostać zasiłek chorobowy, złożyć do ZUS wniosek o zasiłek "
            "chorobowy ZAS-53. Zasiłek wypłaca ZUS."
        ]
        sources = [line_sources]
    else:
        title, label = "Dokumenty do zasiłku chorobowego", "Zasiłek chorobowy: dokumenty"
        rule = [
            "Mama pracuje na umowie zlecenia: na zwolnieniu powinna powstrzymać się od pracy "
            "zawodowej, a aby dostać zasiłek chorobowy, złożyć odpowiednie dokumenty do ZUS albo "
            "do płatnika składek (zleceniodawcy).",
            line,
        ]
        sources = [a.sick_contract.sources, line_sources]
    rule.append(
        "Materiały nie podają terminu: pokazujemy je na dzień, od którego przysługuje zasiłek."
    )
    return [
        Document(
            id="sick-benefit-request",
            label=label,
            title=title,
            needed_by=first.start,
            done=False,
            rule=" ".join(rule),
            segment_id=first.id,
            sources=merge_sources(*sources),
        )
    ]


def _job_loss_documents(
    scenario: Scenario, timeline: Timeline, params: Params, today: dt.date
) -> list[Document]:
    """Guide page 4: after a termination that broke the law, the benefit until the birth needs a
    final court judgment. The guide names no document for the employer's bankruptcy,
    liquidation or death."""
    loss = scenario.job_loss
    segment = _segment(timeline, JOB_LOSS_SEGMENT)
    if loss is None or loss.reason != "unlawful" or segment is None or segment.end < today:
        return []
    done = loss.court_confirmed is True
    rule = (
        "Zasiłek w wysokości zasiłku macierzyńskiego po rozwiązaniu umowy o pracę z naruszeniem "
        "przepisów prawa przysługuje, gdy fakt ten potwierdzi prawomocny wyrok sądu."
    )
    rule += (
        " Sąd już to potwierdził."
        if done
        else " Materiały nie podają, do kiedy wyrok musi zapaść: pokazujemy go na dzień, od "
        "którego przysługiwałby zasiłek."
    )
    return [
        Document(
            id=COURT_JUDGMENT,
            label="Wyrok sądu",
            title="Prawomocny wyrok sądu o naruszeniu prawa przy rozwiązaniu umowy",
            needed_by=segment.start,
            done=done,
            rule=rule,
            segment_id=JOB_LOSS_SEGMENT,
            sources=params.pregnancy.job_loss_unlawful.sources,
        )
    ]


# Requests.


def _segment(timeline: Timeline, segment_id: str) -> Segment | None:
    return next((s for s in timeline.segments if s.id == segment_id), None)


def _by(
    deadline: dt.date, days: int, before: str, today: dt.date, *, movable: bool
) -> tuple[dt.date, str]:
    """When a request with a Labour Code deadline is due, and the sentence that says so.
    `before` completes "co najmniej N dni …", e.g. "przed rozpoczęciem urlopu (01.08.2027)"."""
    if deadline >= today:
        return deadline, f"Najpóźniej {fmt(deadline)}: co najmniej {days} dni {before}."
    if movable:
        earliest = today + days * DAY
        return today, (
            f"Wniosek składa się co najmniej {days} dni {before}, więc dla tego dnia termin "
            f"minął {fmt(deadline)}. Złożony dziś jest w terminie dla urlopu od {fmt(earliest)}."
        )
    return deadline, (
        f"Termin minął {fmt(deadline)}: wniosek składa się co najmniej {days} dni {before}."
    )


def _requests(
    scenario: Scenario, timeline: Timeline, params: Params, today: dt.date
) -> list[Document]:
    documents: list[Document] = []
    if _covered(scenario, "mother"):
        if scenario.mothers_work == "employment" and not _after_job_loss(scenario, "mother"):
            documents += _employee_mother(scenario, timeline, params, today)
        else:
            documents += _zam(scenario, timeline, params, today, "mother")
    if _covered(scenario, "father") and any(s.lane == "father" for s in timeline.segments):
        if scenario.fathers_work == "employment":
            documents += _employee_father(scenario, timeline, params, today)
        else:
            documents += _zam(scenario, timeline, params, today, "father")
    return documents


def _employee_mother(
    scenario: Scenario, timeline: Timeline, params: Params, today: dt.date
) -> list[Document]:
    a = params.applications
    documents = []
    prenatal = _segment(timeline, "maternity-prenatal")
    maternity = _segment(timeline, "maternity")
    first = prenatal or maternity
    last = maternity or prenatal
    parental = _segment(timeline, "parental")
    if first is not None and last is not None and last.end >= today:
        right_after = (
            parental is not None and maternity is not None and parental.start == maternity.end + DAY
        )
        payer, payer_sources = payer_line(scenario, "mother", params)
        starts = "zaczyna się" if first.start >= today else "zaczął się"
        rule = [
            f"Mama składa go pracodawcy. Urlop {starts} {fmt(first.start)}; materiały nie "
            "podają terminu tego wniosku, więc pokazujemy go na ten dzień."
        ]
        sources = [a.employee_request.sources]
        if right_after:
            rule.append(
                "Jeśli zaraz po urlopie macierzyńskim mama chce wziąć urlop rodzicielski, może "
                "złożyć jeden wniosek o oba urlopy."
            )
            sources.append(a.one_request.sources)
        rule.append(payer)
        sources += [a.employer_pays_or_z3.sources, payer_sources]
        rule, sources = _attachments(scenario, rule, sources, params, stillbirth=True)
        documents.append(
            Document(
                id="maternity-request",
                label="Wniosek: urlop macierzyński",
                title="Wniosek o urlop macierzyński",
                needed_by=first.start,
                done=False,
                rule=" ".join(rule),
                segment_id=first.id,
                sources=merge_sources(*sources),
            )
        )
    supplementary = _segment(timeline, "supplementary")
    if supplementary is not None and supplementary.lane == "mother":
        documents += _supplementary_request(supplementary, "mother", params, today)
    if parental is not None and parental.end >= today:
        p = a.parental_days_before.value
        needed_by, when = _by(
            parental.start - p * DAY,
            p,
            f"przed rozpoczęciem urlopu ({fmt(parental.start)})",
            today,
            movable=True,
        )
        rule = [f"Mama składa go pracodawcy. {when}"]
        sources = [a.parental_days_before.sources]
        before = next((s for s in timeline.segments if s.end == parental.start - DAY), None)
        if before is not None and before.id in ("maternity", "maternity-resumed"):
            rule.append(
                "Jeśli bierze go bezpośrednio po urlopie macierzyńskim, może o niego wnioskować "
                "razem z urlopem macierzyńskim, w jednym wniosku."
            )
            sources.append(a.one_request.sources)
        if scenario.za_zyciem:
            rule.append("Do wniosku dołącza się zaświadczenie „Za życiem”.")
            sources.append(a.attachments.sources)
        documents.append(
            Document(
                id="parental-request",
                label="Wniosek: urlop rodzicielski",
                title="Wniosek o urlop rodzicielski",
                needed_by=needed_by,
                done=False,
                rule=" ".join(rule),
                segment_id="parental",
                sources=merge_sources(*sources),
            )
        )
    his = _segment(timeline, "maternity-father")
    if (
        scenario.father_takes_over
        and scenario.mother_event is None
        and his is not None
        and maternity is not None
        and maternity.end + DAY >= today
    ):
        back = maternity.end + DAY
        r = a.resignation_days_before.value
        needed_by, when = _by(
            back - r * DAY, r, f"przed powrotem do pracy ({fmt(back)})", today, movable=False
        )
        rule = [f"Mama składa go pracodawcy, gdy dalszą część urlopu przejmuje tata. {when}"]
        if (scenario.mother_weeks_before_takeover or 14) == 14:
            rule.append("Może też od razu wnioskować tylko o 14 tygodni urlopu.")
        documents.append(
            Document(
                id="maternity-resignation",
                label="Rezygnacja z części urlopu",
                title="Wniosek o rezygnację z dalszej części urlopu macierzyńskiego",
                needed_by=needed_by,
                done=False,
                rule=" ".join(rule),
                segment_id="maternity",
                sources=merge_sources(
                    a.resignation_days_before.sources,
                    params.father.takeover_starts_after.sources,
                ),
            )
        )
    return documents


def _supplementary_request(
    supplementary: Segment, parent: Parent, params: Params, today: dt.date
) -> list[Document]:
    """Art. 180² § 4-5: at least 21 days before maternity leave ends, with the hospital's
    certificate. Supplementary leave starts right after maternity leave."""
    if supplementary.end < today:
        return []
    a = params.applications
    days = a.supplementary_days_before_end.value
    maternity_end = supplementary.start - DAY
    needed_by, when = _by(
        maternity_end - days * DAY,
        days,
        f"przed końcem urlopu macierzyńskiego ({fmt(maternity_end)})",
        today,
        movable=False,
    )
    return [
        Document(
            id="supplementary-request",
            label="Wniosek: urlop uzupełniający",
            title="Wniosek o uzupełniający urlop macierzyński",
            needed_by=needed_by,
            done=False,
            rule=(
                f"{WHO[parent]} składa go pracodawcy. {when} Do wniosku dołącza się "
                "zaświadczenie ze szpitala, w którym przebywało dziecko."
            ),
            segment_id="supplementary",
            sources=merge_sources(
                a.supplementary_days_before_end.sources,
                a.supplementary_hospital_certificate.sources,
            ),
        )
    ]


def _employee_father(
    scenario: Scenario, timeline: Timeline, params: Params, today: dt.date
) -> list[Document]:
    a = params.applications
    documents = []
    his = _segment(timeline, "maternity-father")
    if his is not None and his.end >= today:
        event = scenario.mother_event
        if event is None or event.kind == "incapacity":
            # Art. 180 § 9: taking over after 14 weeks (§ 4-5) or the mother's incapacity (§ 6-7).
            days = a.father_maternity_days_before.value
            needed_by, when = _by(
                his.start - days * DAY,
                days,
                f"przed rozpoczęciem tej części urlopu ({fmt(his.start)})",
                today,
                movable=False,
            )
            sources = a.father_maternity_days_before.sources
        else:
            # Art. 180 § 16: the mother in hospital, dead or gone; no deadline.
            needed_by = his.start
            when = (
                f"Jego część urlopu zaczyna się {fmt(his.start)}; Kodeks pracy nie podaje w tej "
                "sytuacji terminu wniosku."
            )
            sources = a.father_maternity_on_request.sources
        documents.append(
            Document(
                id="maternity-father-request",
                label="Wniosek taty: macierzyński",
                title="Wniosek taty o część urlopu macierzyńskiego",
                needed_by=needed_by,
                done=False,
                rule=f"Tata składa go swojemu pracodawcy. {when}",
                segment_id="maternity-father",
                sources=sources,
            )
        )
    supplementary = _segment(timeline, "supplementary")
    if supplementary is not None and supplementary.lane == "father":
        documents += _supplementary_request(supplementary, "father", params, today)
    paternity = _segment(timeline, "paternity")
    if paternity is not None and paternity.end >= today:
        days = a.paternity_days_before.value
        needed_by, when = _by(
            paternity.start - days * DAY,
            days,
            f"przed rozpoczęciem urlopu ({fmt(paternity.start)})",
            today,
            movable=True,
        )
        documents.append(
            Document(
                id="paternity-request",
                label="Wniosek: urlop ojcowski",
                title="Wniosek o urlop ojcowski",
                needed_by=needed_by,
                done=False,
                rule=f"Tata składa go swojemu pracodawcy. {when}",
                segment_id="paternity",
                sources=a.paternity_days_before.sources,
            )
        )
    parental = _segment(timeline, "parental-father")
    if parental is not None and parental.end >= today:
        days = a.parental_days_before.value
        needed_by, when = _by(
            parental.start - days * DAY,
            days,
            f"przed rozpoczęciem urlopu ({fmt(parental.start)})",
            today,
            movable=True,
        )
        documents.append(
            Document(
                id="parental-father-request",
                label="Wniosek taty: rodzicielski",
                title="Wniosek taty o urlop rodzicielski",
                needed_by=needed_by,
                done=False,
                rule=f"Tata składa go swojemu pracodawcy. {when}",
                segment_id="parental-father",
                sources=a.parental_days_before.sources,
            )
        )
    return documents


def _zam(
    scenario: Scenario, timeline: Timeline, params: Params, today: dt.date, parent: Parent
) -> list[Document]:
    """A parent who is not an employee files ZAM: straight with ZUS with a business; on a
    contract of mandate the payer or ZUS determines the benefit, with Z-3a from the payer."""
    a = params.applications
    if parent == "mother":
        periods = [s for s in timeline.segments if s.lane == "mother" and s.id in MOTHER_LEAVE]
    else:
        periods = [s for s in timeline.segments if s.lane == "father"]
    periods = [s for s in periods if s.end >= today]
    if not periods:
        return []
    first = min(periods, key=lambda s: s.start)
    who = WHO[parent]
    work = _work(scenario, parent)
    loss = after_job_loss(scenario) if parent == "mother" else None
    if loss is not None:
        rule = [
            f"Mama nie jest już pracownicą: zatrudnienie ustało {fmt(loss.ended_on)}. Wniosek "
            "o zasiłek macierzyński (ZAM) składa bezpośrednio do ZUS, który wypłaca zasiłki za "
            "okres po ustaniu ubezpieczenia."
        ]
        sources = [a.non_employee_zam.sources, params.pregnancy.zus_after_insurance.sources]
    elif work == "business":
        rule = [
            f"{who} nie jest pracownikiem i prowadzi własną firmę, więc składa wniosek "
            "o zasiłek macierzyński (ZAM) bezpośrednio do ZUS."
            if parent == "father"
            else "Mama nie jest pracownicą i prowadzi własną firmę, więc składa wniosek o zasiłek "
            "macierzyński (ZAM) bezpośrednio do ZUS."
        ]
        sources = [a.non_employee_zam.sources]
    else:
        payer = "płatnik składek (zleceniodawca)"
        limit = a.payer_more_than_insured.value
        match who_pays(scenario, parent):
            case "payer":
                decides = (
                    f"Prawo do zasiłku ustala i zasiłek wypłaca {payer}: zgłasza do ubezpieczenia "
                    f"chorobowego więcej niż {limit} osób."
                )
            case "zus":
                decides = (
                    "Prawo do zasiłku ustala ZUS; płatnik składek przesyła do ZUS zaświadczenie "
                    "płatnika składek Z-3a."
                )
            case _:
                decides = (
                    f"Prawo do zasiłku ustala {payer}, jeśli jest uprawniony do wypłaty zasiłku "
                    f"(zgłasza do ubezpieczenia chorobowego więcej niż {limit} osób), albo ZUS; "
                    "wtedy płatnik przesyła do ZUS zaświadczenie płatnika składek Z-3a."
                )
        rule = [f"{who} pracuje na umowie zlecenia i składa wniosek ZAM. {decides}"]
        sources = [a.contract_zam.sources, a.paid_by_payer_or_zus.sources]
        if who_pays(scenario, parent) != "zus":
            sources.append(a.payer_more_than_insured.sources)
    rule.append(
        "ZAM to wniosek o zasiłek macierzyński za okres urlopu macierzyńskiego i rodzicielskiego "
        "(formularz ZUR połączono z nim 24 października 2026 r.)."
        if parent == "mother"
        else "ZAM to wniosek o zasiłek macierzyński za okres urlopu macierzyńskiego "
        "i rodzicielskiego, a od 24 października 2026 r. także ojcowskiego (formularze ZUR i ZAO "
        "połączono z ZAM)."
    )
    rule.append(
        "Materiały nie podają terminu tego wniosku: pokazujemy go na dzień, od którego "
        "przysługuje zasiłek."
    )
    sources.append(a.zam_form.sources)
    if parent == "mother":
        supplementary = _segment(timeline, "supplementary")
        hospital = supplementary is not None and supplementary.lane == "mother"
        rule, sources = _attachments(
            scenario, rule, sources, params, stillbirth=True, hospital=hospital
        )
    else:
        supplementary = _segment(timeline, "supplementary")
        hospital = supplementary is not None and supplementary.lane == "father"
        rule, sources = _attachments(scenario, rule, sources, params, hospital=hospital)
    return [
        Document(
            id="maternity-request" if parent == "mother" else "father-benefit-request",
            label="Wniosek ZAM" if parent == "mother" else "Wniosek ZAM taty",
            title="Wniosek o zasiłek macierzyński (ZAM)"
            if parent == "mother"
            else "Wniosek taty o zasiłek macierzyński (ZAM)",
            needed_by=first.start,
            done=False,
            rule=" ".join(rule),
            segment_id=first.id,
            sources=merge_sources(*sources),
        )
    ]


def _attachments(
    scenario: Scenario,
    rule: list[str],
    sources: list[list[SourceRef]],
    params: Params,
    *,
    stillbirth: bool = False,
    hospital: bool = False,
) -> tuple[list[str], list[list[SourceRef]]]:
    """Guide A.4: documents needed for the right or affecting the length of the benefit."""
    needed = []
    if stillbirth and any(loss.stillborn for loss in scenario.losses):
        needed.append("zaświadczenie o martwym urodzeniu")
    if hospital:
        needed.append("zaświadczenie ze szpitala, w którym przebywało dziecko")
    if scenario.za_zyciem:
        needed.append("zaświadczenie „Za życiem”")
    if not needed:
        return rule, sources
    return (
        [*rule, f"Do wniosku dołącza się: {', '.join(needed)}."],
        [*sources, params.applications.attachments.sources],
    )


# Protection.


def _protection_end(scenario: Scenario, timeline: Timeline, params: Params) -> Marker | None:
    """Guide I; art. 177 § 1, § 1¹: an employed mother is protected in pregnancy, on maternity
    leave, and from the request for further leave until it ends. The marker is the last day of
    the leave that follows on from maternity leave on the timeline."""
    if scenario.mothers_work != "employment" or not _covered(scenario, "mother"):
        return None
    if scenario.mother_event is not None and scenario.mother_event.kind == "death":
        return None
    if _after_job_loss(scenario, "mother"):
        return None  # no longer employed: the benefit after the insurance ended
    a = params.applications
    leave = sorted(
        (s for s in timeline.segments if s.lane == "mother" and s.id in MOTHER_LEAVE),
        key=lambda s: s.start,
    )
    if not any(s.id == "maternity" for s in leave):
        return None
    chain = [leave[0]]
    for segment in leave[1:]:
        if segment.start == chain[-1].end + DAY:
            chain.append(segment)
    end = chain[-1].end
    if end < timeline.today:
        return None
    later = [s for s in leave if s not in chain]
    details = [
        "Wyjątek: przyczyny uzasadniające rozwiązanie umowy bez wypowiedzenia z winy pracownicy, "
        "gdy zgodzi się na to reprezentująca ją zakładowa organizacja związkowa."
    ]
    options = [_leave_name(s) for s in chain if s.tone == "option"]
    if options:
        details.append(
            f"{' i '.join(options).capitalize()}: do wyboru. Ochrona obejmuje "
            f"{'go' if len(options) == 1 else 'je'} od dnia złożenia wniosku o urlop."
        )
    if later:
        details.append(
            f"Później ochrona wraca od dnia złożenia wniosku o {_leave_name(later[0])} do dnia "
            "jego zakończenia."
        )
    _, early, _ = a.protection_early_request_days.value
    details.append(
        "Jeśli wniosek o urlop uzupełniający albo rodzicielski zostanie złożony wcześniej niż "
        f"w terminie z Kodeksu pracy, zakaz zaczyna obowiązywać {early} dni przed tym urlopem."
    )
    if not timeline.child_born:
        details.append("Liczymy od przewidywanej daty porodu.")
    return Marker(
        id="protection-end",
        lane="child",
        label="Ochrona do",
        title="Koniec ochrony mamy przed zwolnieniem",
        date=end,
        summary=(
            "W ciąży i w czasie urlopu macierzyńskiego, a także od dnia złożenia wniosku o kolejny "
            "urlop do dnia jego zakończenia, pracodawca nie może wypowiedzieć ani rozwiązać umowy "
            "o pracę z mamą ani prowadzić do tego przygotowań. Przy urlopach jak na osi ochrona "
            f"trwa do {fmt(end)}."
        ),
        details=details,
        sources=merge_sources(a.protection.sources, a.protection_early_request_days.sources),
    )


def _leave_name(segment: Segment) -> str:
    """ "urlop rodzicielski", from "Urlop rodzicielski — do wyboru"."""
    name = segment.title.split(" —")[0]
    return name[0].lower() + name[1:]


def _fixed_term(scenario: Scenario, timeline: Timeline, params: Params) -> None:
    """Guide I; art. 177 § 3: while the child is on the way, the due date marker says that an
    employed mother's fixed-term contract is extended until the birth."""
    if timeline.child_born or scenario.mothers_work != "employment" or scenario.job_loss:
        return
    a = params.applications
    timeline.markers = [
        m.model_copy(
            update={
                "details": [
                    *m.details,
                    "Jeśli mama ma umowę o pracę na czas określony albo na okres próbny dłuższy "
                    "niż miesiąc, która skończyłaby się po upływie trzeciego miesiąca ciąży, umowa "
                    "przedłuża się do dnia porodu. Gdy umowę na czas określony przedłużono do dnia "
                    "porodu, po porodzie przysługuje zasiłek macierzyński po ustaniu "
                    "ubezpieczenia.",
                ],
                "sources": merge_sources(
                    m.sources,
                    a.fixed_term_extended.sources,
                    params.pregnancy.fixed_term_after_insurance.sources,
                ),
            }
        )
        if m.id == "due-date"
        else m
        for m in timeline.markers
    ]


def _assumptions(scenario: Scenario, timeline: Timeline) -> list[str]:
    shown = {d.id for d in timeline.documents}
    assumptions = []
    if shown & {
        "supplementary-request",
        "parental-request",
        "maternity-resignation",
        "maternity-father-request",
        "paternity-request",
        "parental-father-request",
    }:
        assumptions.append(
            "Termin „nie krótszy niż 21 dni przed” rozpoczęciem urlopu liczymy tak: wniosek "
            "trzeba złożyć najpóźniej 21. dnia przed pierwszym dniem urlopu (tak samo przy 7 i 14 "
            "dniach)."
        )
    if shown & {"maternity-request", "father-benefit-request"}:
        assumptions.append(
            "Terminu wniosku o urlop macierzyński ani wniosku ZAM materiały nie podają: pokazujemy "
            "go na dzień, w którym zaczyna się urlop (zasiłek)."
        )
    if "father-benefit-request" in shown:
        assumptions.append(
            "Gdzie składa wniosek ZAM osoba, która nie jest pracownikiem, Przewodnik mówi przy "
            "mamie; dla taty przyjmujemy to samo."
        )
    if "business" in (scenario.mothers_work, scenario.fathers_work):
        assumptions.append(
            "Przy własnej firmie wniosek ZAM składa się bezpośrednio do ZUS, więc przyjmujemy, "
            "że zasiłek wypłaca ZUS."
        )
    # Sick leave in pregnancy and the benefit after losing the job (guide pages 3-4).
    if "sick-leave-notice" in shown:
        assumptions.append(
            "Kiedy poinformować pracodawcę o nieobecności, Przewodnik odsyła do przepisów "
            "Kodeksu pracy, których nie ma w materiałach: pokazujemy to na pierwszy dzień "
            "zwolnienia."
        )
    if "sick-benefit-request" in shown:
        assumptions.append(
            "Terminu dokumentów do zasiłku chorobowego materiały nie podają: pokazujemy je na "
            "dzień, od którego przysługuje zasiłek."
            + (
                " Wniosek ZAS-53 przy własnej firmie idzie do ZUS, więc przyjmujemy, że zasiłek "
                "chorobowy wypłaca ZUS."
                if scenario.mothers_work == "business"
                else ""
            )
        )
    if any(d.id == COURT_JUDGMENT and not d.done for d in timeline.documents):
        assumptions.append(
            "Do kiedy musi zapaść wyrok sądu, Przewodnik nie podaje: pokazujemy go na dzień, od "
            "którego przysługiwałby zasiłek w wysokości zasiłku macierzyńskiego."
        )
    if any(s.id == JOB_LOSS_SEGMENT for s in timeline.segments):
        assumptions.append(
            "Jaki wniosek złożyć o zasiłek w wysokości zasiłku macierzyńskiego i kto go wypłaca, "
            "Przewodnik nie podaje, więc oś tego nie pokazuje."
        )
    return assumptions


# The case explanation: what to file, who pays, the protection.


def application_notes(scenario: Scenario, timeline: Timeline, params: Params) -> list[CaseNote]:
    """After "Co policzyliśmy": the protection, who pays, what to file and by when."""
    notes = [
        _protection_note(scenario, timeline, params),
        _payer_note(scenario, timeline, params),
        _applications_note(scenario, timeline),
    ]
    return [note for note in notes if note is not None]


def _has_leave(timeline: Timeline, parent: Parent) -> bool:
    if parent == "father":
        return any(s.lane == "father" for s in timeline.segments)
    return any(s.lane == "mother" and s.id in BENEFIT_PERIODS for s in timeline.segments)


def _protection_note(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote | None:
    a = params.applications
    mother = scenario.mothers_work
    alive = scenario.mother_event is None or scenario.mother_event.kind != "death"
    father = (
        scenario.fathers_work == "employment"
        and _covered(scenario, "father")
        and _has_leave(timeline, "father")
    )
    his = (
        " Tatę, który pracuje na umowie o pracę, chroni to samo od dnia złożenia wniosku "
        "o urlop do dnia jego zakończenia."
    )
    employed = not _after_job_loss(scenario, "mother")
    if alive and employed and mother == "employment" and _has_leave(timeline, "mother"):
        marker = next((m for m in timeline.markers if m.id == "protection-end"), None)
        text = (
            "Mama pracuje na umowie o pracę, więc w ciąży i w czasie urlopu macierzyńskiego, "
            "a także od dnia złożenia wniosku o kolejny urlop do dnia jego zakończenia, "
            "pracodawca nie może wypowiedzieć ani rozwiązać z nią umowy ani się do tego "
            "przygotowywać (wyjątek: rozwiązanie umowy z jej winy za zgodą związku zawodowego)."
        )
        sources = [a.protection.sources]
        if marker is not None:
            text += f" Przy urlopach jak na osi ochrona trwa do {long_date(marker.date)}."
        if not timeline.child_born:
            text += (
                " Umowa na czas określony albo na okres próbny dłuższy niż miesiąc, która "
                "skończyłaby się po upływie trzeciego miesiąca ciąży, przedłuża się do dnia "
                "porodu; po porodzie przysługuje wtedy zasiłek macierzyński po ustaniu "
                "ubezpieczenia."
            )
            sources += [
                a.fixed_term_extended.sources,
                params.pregnancy.fixed_term_after_insurance.sources,
            ]
        return CaseNote(
            id="protection",
            kind="right",
            title="Ochrona przed zwolnieniem",
            text=text + (his if father else ""),
            sources=merge_sources(*sources),
        )
    if alive and mother in ("contract", "business") and _covered(scenario, "mother"):
        how = "pracuje na umowie zlecenia" if mother == "contract" else "prowadzi własną firmę"
        return CaseNote(
            id="protection",
            kind="risk",
            title="Bez szczególnej ochrony z Kodeksu pracy",
            text=(
                "Szczególna ochrona przed wypowiedzeniem umowy w ciąży i w czasie urlopu dotyczy "
                f"pracowników. Mama {how}, więc jej nie obejmuje." + (his if father else "")
            ),
            sources=merge_sources(
                a.protection_employees_only.sources, a.protection.sources if father else []
            ),
        )
    if father:
        return CaseNote(
            id="protection",
            kind="right",
            title="Ochrona taty przed zwolnieniem",
            text=(
                "Tata pracuje na umowie o pracę: od dnia złożenia wniosku o urlop do dnia jego "
                "zakończenia pracodawca nie może wypowiedzieć ani rozwiązać z nim umowy ani się do "
                "tego przygotowywać."
            ),
            sources=a.protection.sources,
        )
    return None


def _payer_note(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote | None:
    a = params.applications
    parents: list[Parent] = [
        p for p in ("mother", "father") if _covered(scenario, p) and _has_leave(timeline, p)
    ]
    sick = _sick_payer_lines(scenario, timeline, params)
    if not parents and not sick:
        return None
    lines = []
    sources = []
    # Sick leave in pregnancy comes first: it is before the birth.
    for line, line_sources in sick:
        lines.append(line)
        sources.append(line_sources)
    for parent in parents:
        line, line_sources = payer_line(scenario, parent, params)
        lines.append(line)
        sources.append(line_sources)
    sick_by_size = scenario.mothers_work != "business" and any(
        _is_sick_benefit(s) for s in timeline.segments
    )
    if any(who_pays(scenario, p) == "payer-or-zus" for p in parents) or (
        sick_by_size and who_pays(scenario, "mother") == "payer-or-zus"
    ):
        lines.append(
            "Liczbę ubezpieczonych ustala się według stanu na 30 listopada poprzedniego roku."
        )
        sources.append(a.payer_count_day.sources)
    if not parents:
        title = "Kto płaci za zwolnienie lekarskie"
    elif len(parents) == 1 and (parents[0] == "mother" or not sick):
        parent = parents[0]
        title = {
            "payer": f"Zasiłek {WHOSE[parent]} wypłaca "
            + ("pracodawca" if _work(scenario, parent) == "employment" else "płatnik składek"),
            "zus": f"Zasiłek {WHOSE[parent]} wypłaca ZUS",
            "payer-or-zus": f"Kto wypłaca zasiłek {WHOSE[parent]}",
        }[who_pays(scenario, parent)]
    else:
        title = "Kto wypłaca zasiłek"
    return CaseNote(
        id="payer",
        kind="computed",
        title=title,
        text=" ".join(lines),
        sources=merge_sources(*sources),
    )


def _sick_payer_lines(
    scenario: Scenario, timeline: Timeline, params: Params
) -> list[tuple[str, list[SourceRef]]]:
    """Sick leave in pregnancy: the employer's days, then the sickness benefit."""
    sick = [s for s in timeline.segments if _is_sick(s)]
    if scenario.mothers_work not in WORKING or not sick:
        return []
    lines = []
    if any(s.id.startswith(SICK_PAY) for s in sick):
        p = params.pregnancy
        limit = p.employer_days_from_50 if scenario.mother_over_50 else p.employer_days
        lines.append(
            (
                "Za zwolnienie lekarskie w ciąży wynagrodzenie chorobowe za pierwsze "
                f"{limit.value} dni niezdolności do pracy w roku kalendarzowym wypłaca mamie "
                "pracodawca.",
                limit.sources,
            )
        )
    if any(_is_sick_benefit(s) for s in sick):
        lines.append(sick_payer_line(scenario, params))
    return lines


def _destination(document: Document, scenario: Scenario) -> str:
    """Where the request goes, in a few words."""
    if document.id == "father-benefit-request":
        work = scenario.fathers_work
    elif document.id in ("maternity-request", "sick-benefit-request"):
        work = scenario.mothers_work
        if _after_job_loss(scenario, "mother"):
            return "do ZUS"
    else:
        return "do pracodawcy"
    match work:
        case "employment":
            return "do pracodawcy"
        case "business":
            return "do ZUS"
        case _:
            return "do płatnika składek albo do ZUS"


def _applications_line(document: Document, scenario: Scenario) -> str:
    match document.id:
        case "sick-leave-notice":
            return (
                f"{document.title} — pierwszego dnia zwolnienia, {long_date(document.needed_by)}."
            )
        case "court-judgment":
            return (
                f"{document.title}: bez niego zasiłek w wysokości zasiłku macierzyńskiego nie "
                "przysługuje."
            )
        case _:
            return (
                f"{document.title} — {_destination(document, scenario)}, do "
                f"{long_date(document.needed_by)}."
            )


def _applications_note(scenario: Scenario, timeline: Timeline) -> CaseNote | None:
    listed = (*REQUESTS, *SICK_DOCUMENTS, COURT_JUDGMENT)
    documents = sorted(
        (d for d in timeline.documents if d.id in listed and not d.done),
        key=lambda d: d.needed_by,
    )
    if not documents:
        return None
    lines = [_applications_line(d, scenario) for d in documents]
    return CaseNote(
        id="applications",
        kind="computed",
        title="Co złożyć i do kiedy",
        text=" ".join(lines) + " Szczegóły każdego wniosku są na osi czasu, w ścieżce dokumentów.",
        sources=merge_sources(*(d.sources for d in documents)),
    )
