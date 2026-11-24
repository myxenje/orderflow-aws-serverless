from src.functions.coletor.service import publish_pending_events


if __name__ == "__main__":
    published_count = publish_pending_events()

    print(
        f"Publicação concluída. "
        f"Eventos enviados: {published_count}"
    )