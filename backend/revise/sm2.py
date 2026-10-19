from __future__ import annotations


def calculate_next_review(confidence, difficulty, ef, interval, rep_number):
    """Return the next SM-2 state for a single review submission."""
    difficulty_key = str(difficulty or 'Medium').capitalize()
    difficulty_multiplier = {
        'Easy': 1.0,
        'Medium': 1.3,
        'Hard': 1.6,
    }.get(difficulty_key, 1.0)

    current_ef = max(1.3, float(ef or 2.5))
    safe_interval = max(0, int(interval or 0))
    safe_rep_number = max(0, int(rep_number or 0))

    if confidence < 3:
        return {
            'interval': 1,
            'easiness_factor': current_ef,
            'repetition_number': 0,
            'difficulty_multiplier': difficulty_multiplier,
        }

    updated_ef = current_ef + (0.1 - (5 - confidence) * (0.08 + (5 - confidence) * 0.02))
    updated_ef = max(1.3, updated_ef)

    if safe_rep_number == 0:
        next_interval = 1
    elif safe_rep_number == 1:
        next_interval = 6
    else:
        next_interval = max(1, int(round(safe_interval * updated_ef)))

    next_rep_number = safe_rep_number + 1
    next_interval = max(1, int(round(next_interval * difficulty_multiplier)))

    return {
        'interval': next_interval,
        'easiness_factor': round(updated_ef, 2),
        'repetition_number': next_rep_number,
        'difficulty_multiplier': difficulty_multiplier,
    }
