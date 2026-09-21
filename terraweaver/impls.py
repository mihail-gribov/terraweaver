"""Deterministic method implementations for the core ontology classes.

Keyed by (class_name, method_name) and attached to dynamically built classes by
terraweaver.ontology.build_classes. Kept separate from the JSON specs because a
signature + description alone doesn't determine behavior.
"""
import math

from terraweaver.ontology import world_if_bound



# --- Person ---

def person_send_email(self, subject: str, body: str) -> bool:
    if not self.email:
        raise ValueError(f"{self.full_name} has no email on file")
    print(f"[send_email] to={self.email} subject={subject!r}")
    # The world remembers what was sent to whom — "when did I last write to Anna?" is a
    # question about the world like any other.
    from datetime import datetime, timezone
    self.describe(f"email sent: {subject}", when=datetime.now(timezone.utc), permanent=True)
    return True


def person_add_fact(self, predicate: str, value: str, confidence: float = 1.0):
    # Saved here: facts is derived from Preference.subject, so nothing else carries it to storage.
    Preference = type(self)._classes["Preference"]
    fact = Preference(subject=self, predicate=predicate, value=value, confidence=confidence)
    if world_if_bound() is not None:  # a fixture being built saves what it gets back
        fact.save()
    return fact


# Person.research / Organization.research (Tavily grounding) are deliberately left
# unregistered: no real implementation exists yet, so they fall back to the generic
# stub in ontology.py and raise NotImplementedError. A print-and-no-op placeholder
# would let the agent believe grounding happened when it didn't.


# --- Organization ---

def organization_add_contact(self, person) -> None:
    # employees is derived from Person.organization; setting that is all there is to do.
    person.organization = self


# --- Project ---

def project_add_participant(self, person) -> None:
    if person not in (self.participants or []):
        self.participants = (self.participants or []) + [person]


def project_mark_done(self) -> None:
    self.status = "done"


def project_add_note(self, text: str):
    Idea = type(self)._classes["Idea"]
    title = text if len(text) <= 40 else text[:37] + "..."
    note = Idea(title=title, content=text, related_to=[self])
    if world_if_bound() is not None:
        note.save()
    return note


# --- Place ---

def place_distance_to(self, other) -> float:
    if not self.coordinates or not other.coordinates:
        raise ValueError("both places need 'coordinates' set to compute distance")
    lat1, lon1 = self.coordinates["lat"], self.coordinates["lon"]
    lat2, lon2 = other.coordinates["lat"], other.coordinates["lon"]
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# --- Event ---

def event_cancel(self) -> None:
    self.status = "cancelled"


def event_reschedule(self, new_start, new_end=None) -> None:
    self.start_time = new_start
    if new_end is not None:
        self.end_time = new_end


def event_add_participant(self, person) -> None:
    if person not in (self.participants or []):
        self.participants = (self.participants or []) + [person]


# --- Idea ---

def idea_link_to(self, entity) -> None:
    if entity not in (self.related_to or []):
        self.related_to = (self.related_to or []) + [entity]


# --- Preference ---

def preference_update_value(self, new_value: str) -> None:
    self.value = new_value


def preference_confirm(self) -> None:
    self.confidence = 1.0


# --- Vacancy ---

def vacancy_apply(self) -> None:
    from datetime import datetime, timezone

    self.status = "applied"
    self.applied_at = datetime.now(timezone.utc)


def vacancy_matches_stack(self, skills: list) -> float:
    if not skills:
        return 0.0
    have = set(s.lower() for s in (self.stack or []))
    want = set(s.lower() for s in skills)
    return len(have & want) / len(want)


IMPLS = {
    ("Person", "send_email"): person_send_email,
    ("Organization", "add_contact"): organization_add_contact,
    ("Project", "add_participant"): project_add_participant,
    ("Project", "mark_done"): project_mark_done,
    ("Project", "add_note"): project_add_note,
    ("Person", "add_fact"): person_add_fact,
    ("Place", "distance_to"): place_distance_to,
    ("Event", "cancel"): event_cancel,
    ("Event", "reschedule"): event_reschedule,
    ("Event", "add_participant"): event_add_participant,
    ("Idea", "link_to"): idea_link_to,
    ("Preference", "update_value"): preference_update_value,
    ("Preference", "confirm"): preference_confirm,
    ("Vacancy", "apply"): vacancy_apply,
    ("Vacancy", "matches_stack"): vacancy_matches_stack,
}
