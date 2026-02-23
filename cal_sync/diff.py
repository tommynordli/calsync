from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    uid: str
    start: str
    end: str
    all_day: bool


def compute_diff(
    events: list[Event],
    state_entries: dict[str, dict],
) -> tuple[list[Event], list[tuple[Event, str]], list[tuple[str, str]]]:
    current_uids = {e.uid for e in events}

    to_create: list[Event] = []
    to_update: list[tuple[Event, str]] = []
    to_delete: list[tuple[str, str]] = []

    for event in events:
        if event.uid not in state_entries:
            to_create.append(event)
        else:
            entry = state_entries[event.uid]
            if event.start != entry["start"] or event.end != entry["end"] or event.all_day != entry["all_day"]:
                to_update.append((event, entry["google_event_id"]))

    for uid, entry in state_entries.items():
        if uid not in current_uids:
            to_delete.append((uid, entry["google_event_id"]))

    return to_create, to_update, to_delete
