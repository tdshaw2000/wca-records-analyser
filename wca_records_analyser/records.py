"""Detection of personal records within a competitor's results."""


def personal_record_flags(singles):
    """Flag each single that beats every preceding single in chronological order."""
    flags = []
    best_so_far = None
    for single in singles:
        is_attempted = single > 0
        is_record = is_attempted and (best_so_far is None or single < best_so_far)
        flags.append(is_record)
        if is_record:
            best_so_far = single
    return flags
