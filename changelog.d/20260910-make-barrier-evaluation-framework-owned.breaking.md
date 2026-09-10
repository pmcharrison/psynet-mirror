Custom ``Barrier`` subclasses must use ``check_waiting_participants()`` and ``choose_who_to_release()`` instead of overriding ``check()`` or querying waiting participants directly.
