from settings import load_config

from src.database.settings import set_setting


def import_settings() -> None:
    config = load_config()

    if not config:
        print("Config je prázdný, není co importovat.")
        return

    for key, value in config.items():
        set_setting(str(key), str(value))

    print(f"Importováno nastavení: {len(config)}")


if __name__ == "__main__":
    import_settings()