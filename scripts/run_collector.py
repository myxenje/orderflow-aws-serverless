from src.functions.coletor.service import publish_pending_events


def main():
    published_count = publish_pending_events()

    print(
        f"Eventos publicados com sucesso: {published_count}"
    )


if __name__ == "__main__":
    main()