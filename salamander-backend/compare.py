from explain import _vector, _cosine, fit_percentile

COMPARE_BANDS = [(95, "closely related"), (85, "related"), (65, "loosely related"), (35, "not much alike")]
COMPARE_FLOOR = "very different"

def book_vector(book):
    return _vector(book.get("embedding"))

def brief(book):
    return {"id": book.get("id"), "title": book.get("title") or "", "author": book.get("author"),
            "cover_url": book.get("cover_url")}

def compare_label(percentile):
    if percentile is None:
        return None
    for floor, label in COMPARE_BANDS:
        if percentile >= floor:
            return label
    return COMPARE_FLOOR

def _tags(book):
    seen = []
    for t in book.get("genre_tags") or []:
        if t and t not in seen:
            seen.append(t)
    return seen

def _join(items):
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]

def compare_books(a, b, sims_a=None, sims_b=None, themes_fn=None):
    if a.get("id") == b.get("id"):
        raise ValueError("Pick two different books.")
    result = {"books": {"a": brief(a), "b": brief(b)}}
    vec_a, vec_b = book_vector(a), book_vector(b)
    missing = [name for name, vec in (("a", vec_a), ("b", vec_b)) if vec is None]
    if missing:
        return {**result, "comparable": False, "missing": missing}

    similarity = _cosine(vec_a, vec_b)
    p_a, p_b = fit_percentile(similarity, sims_a), fit_percentile(similarity, sims_b)
    percentiles = [p for p in (p_a, p_b) if p is not None]
    percentile = int(round(sum(percentiles) / len(percentiles))) if percentiles else None
    label = compare_label(percentile)

    tags_a, tags_b = _tags(a), _tags(b)
    shared = [t for t in tags_a if t in tags_b]
    only_a = [t for t in tags_a if t not in tags_b]
    only_b = [t for t in tags_b if t not in tags_a]

    themes = []
    if themes_fn is not None:
        try:
            themes = list(themes_fn() or [])
        except Exception:
            themes = []

    title_a, title_b = result["books"]["a"]["title"], result["books"]["b"]["title"]
    if label:
        how = "nearly all" if percentile >= 99 else f"about {percentile}%"
        summary = (f"{title_a} and {title_b} are {label}—more alike than {how} "
                    f"of the catalog is to either one.")
    else:
        summary = f"{title_a} and {title_b} have a similarity of {round(similarity, 2)}."
    if shared:
        noun = "genre" if len(shared) == 1 else "genres"
        summary += f" They share the {noun} {_join(shared)}."
    if themes:
        summary += f" Themes in common: {_join(themes)}."

    return {**result, "comparable": True, "similarity": round(similarity, 3), "percentile": percentile,
            "label": label, "shared_tags": shared, "only_a": only_a, "only_b": only_b, 
            "themes": themes, "summary": summary}