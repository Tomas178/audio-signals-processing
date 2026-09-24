"""Adaptive time-axis unit selection for waveform display (requirement 4).

The time axis of a signal is shown in the unit that best fits its duration:
milliseconds for very short signals, then seconds, minutes and hours.
"""

from __future__ import annotations

# (label, seconds-per-unit). A time in seconds is converted to the chosen unit
# by dividing it by ``seconds_per_unit``.
_MILLISECOND = ("ms", 1e-3)
_SECOND = ("s", 1.0)
_MINUTE = ("min", 60.0)
_HOUR = ("h", 3600.0)


def choose_time_unit(duration_s: float) -> tuple[str, float]:
    """Pick a human-friendly time unit for a signal of ``duration_s`` seconds.

    Returns ``(label, seconds_per_unit)``. Multiply a value in seconds by
    ``1 / seconds_per_unit`` to express it in the chosen unit.
    """
    if duration_s < 1.0:
        return _MILLISECOND
    elif duration_s < 90.0:
        return _SECOND
    elif duration_s < 3600.0:
        return _MINUTE
    return _HOUR


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
