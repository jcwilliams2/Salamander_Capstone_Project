SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}

def flip_name(name):
    if not name:
        return name
    parts = [p.strip() for p in name.split(",")]
    if len(parts) == 2 and all(parts) and parts[1].lower().rstrip(".") not in SUFFIXES:
        return f"{parts[1]} {parts[0]}"
    return name.strip()

def fix_stored_author(author):
    if not author:
        return author
    parts = [p.strip() for p in author.split(",")]
    if len(parts) == 2 and all(parts) and " " not in parts[0]:
        return flip_name(author)
    return author