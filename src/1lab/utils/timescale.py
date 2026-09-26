from __future__ import annotations

from utils.time_unit import TimeUnit


def choose_time_unit(duration_s: float) -> TimeUnit:
    if duration_s < 1.0:
        return TimeUnit.MILLISECOND
    elif duration_s < 90.0:
        return TimeUnit.SECOND
    elif duration_s < 3600.0:
        return TimeUnit.MINUTE
    return TimeUnit.HOUR


def format_duration(seconds: float) -> str:
    """Human-readable duration string for the info bar.

    The unit is chosen from the value *as displayed*, so a duration just under a
    boundary rolls over instead of printing an impossible value (59.999 s gives
    "1 min 0.0 s", not "60.00 s"; 3599.96 s gives "1 h 0 min", not
    "59 min 60.0 s").
    """
    if round(seconds * 1000, 1) < 1000.0:
        return f"{seconds * 1000:.1f} ms"
    elif round(seconds, 2) < 60.0:
        return f"{seconds:.2f} s"
    # Round once to the 0.1 s display precision, then split with integer math so
    # the seconds field can never reach 60.0.
    minutes, tenths = divmod(round(seconds * 10), 600)
    if minutes < 60:
        return f"{minutes} min {tenths / 10:.1f} s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes} min"
