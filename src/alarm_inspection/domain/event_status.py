"""Visual event warning rules, independent of acceptance and export decisions."""


def missing_event_for_marked_device(highlighted: bool, address: int | None,
                                    pending_points: set[int], accepted_points: set[int]) -> bool:
    return bool(highlighted and address not in pending_points and address not in accepted_points)
