def to_instrumental_full_name(full_name: str) -> str:
    parts = full_name.strip().split()

    if len(parts) < 2:
        return full_name

    first_name = parts[0]
    last_name = parts[-1]

    return f"{_first_name_to_instrumental(first_name)} {_last_name_to_instrumental(last_name)}"


def _first_name_to_instrumental(name: str) -> str:
    exceptions = {
        "Ivan": "Ivanem",
        "Jan": "Janem",
        "Petr": "Petrem",
        "Pavel": "Pavlem",
        "Marek": "Markem",
        "Lukáš": "Lukášem",
        "Tomáš": "Tomášem",
        "Martin": "Martinem",
        "Michal": "Michalem",
    }

    if name in exceptions:
        return exceptions[name]

    if name.endswith("ek"):
        return name[:-2] + "kem"

    return name + "em"


def _last_name_to_instrumental(name: str) -> str:
    exceptions = {
        "Korec": "Korcem",
        "Novák": "Novákem",
        "Dvořák": "Dvořákem",
        "Marek": "Markem",
        "Krejčí": "Krejčím",
        "Kočí": "Kočím",
        "Valenta": "Valentou",
        "Petr": "Petrem",
        "Ondřej": "Ondřejem",
        "Tomáš": "Tomášem",
        "Bernát": "Bernátem",
        "Horňák": "Horňákem",
        "Michal": "Michalem",
        "Vaňeček": "Vaňečkem",
        "Mrázek": "Mrázkem",
        "Srch": "Srchem",
    }

    if name in exceptions:
        return exceptions[name]

    if name.endswith("ec"):
        return name[:-2] + "cem"

    if name.endswith("ek"):
        return name[:-2] + "kem"

    if name.endswith("ý"):
        return name[:-1] + "ým"

    return name + "em"